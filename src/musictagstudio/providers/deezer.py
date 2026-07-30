from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .. import __version__
from ..diagnostics import get_diagnostic_logger
from . import http_cache


SEARCH_ENDPOINT = "https://api.deezer.com/search/artist"

DEEZER_API = "https://api.deezer.com"
DEEZER_TIMEOUT_SECONDS = 15
DEEZER_USER_AGENT = f"MusicTagStudio/{__version__}"
MINIMUM_ALBUM_CONFIDENCE = 70


@dataclass(frozen=True)
class DeezerArtistSuggestion:
    name: str
    fans: int = 0


def suggest_artists(
    query: str,
    *,
    limit: int = 25,
) -> list[DeezerArtistSuggestion]:
    query = str(query or "").strip()
    if len(query) < 3:
        return []
    url = f"{SEARCH_ENDPOINT}?{urlencode({'q': query, 'limit': limit})}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"MusicTagStudio/{__version__}",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return []
    suggestions = {
        str(item.get("name") or "").strip(): DeezerArtistSuggestion(
            name=str(item.get("name") or "").strip(),
            fans=int(item.get("nb_fan") or 0),
        )
        for item in payload.get("data", [])
        if str(item.get("name") or "").strip()
    }
    return sorted(
        suggestions.values(),
        key=lambda item: (-item.fans, item.name.casefold()),
    )


# ---------------------------------------------------------------------------
# Album- und Track-Metadaten über die offizielle öffentliche Deezer-API.
#
# Die API (api.deezer.com) ist frei, ohne Login/Token nutzbar und liefert
# vollständige Album-Tracklisten inklusive ISRC, Position, Disc und Label –
# eine saubere, dokumentierte Quelle (wie MusicBrainz), kein Scraping.
# ---------------------------------------------------------------------------


class DeezerProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeezerAlbumCandidate:
    album_id: str
    album: str
    artist: str
    track_count: int
    confidence: int


def _get_json(url: str) -> dict:
    cached = http_cache.load(url)
    if cached is not None:
        return cached

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": DEEZER_USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=DEEZER_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise DeezerProviderError(
            f"Die Deezer-Abfrage ist fehlgeschlagen: {error}"
        ) from error

    # Deezer meldet Fehler als {"error": {...}} mit HTTP 200.
    if isinstance(payload, dict) and payload.get("error"):
        raise DeezerProviderError(
            f"Deezer meldet einen Fehler: {payload['error']}"
        )

    http_cache.store(url, payload)
    return payload


def search_albums(
    album: str,
    artist: str = "",
    *,
    expected_track_count: int | None = None,
    limit: int = 10,
) -> list[DeezerAlbumCandidate]:
    """Sucht Alben über die öffentliche Deezer-API und bewertet die Treffer."""
    logger = get_diagnostic_logger("deezer")
    terms = [part.strip() for part in (artist, album) if part.strip()]

    if not terms:
        return []

    url = (
        f"{DEEZER_API}/search/album?"
        + urlencode(
            {
                "q": " ".join(terms),
                "limit": max(1, min(limit, 50)),
            }
        )
    )

    try:
        payload = _get_json(url)
    except DeezerProviderError as error:
        logger.warning(
            "Deezer-Albumsuche fehlgeschlagen | Album=%r | %s",
            album,
            error,
        )
        return []

    results: list[DeezerAlbumCandidate] = []

    for item in payload.get("data", []) or []:
        album_id = str(item.get("id") or "")

        if not album_id:
            continue

        actual_album = str(item.get("title") or "")
        actual_artist = str((item.get("artist") or {}).get("name") or "")
        track_count = _optional_int(item.get("nb_tracks")) or 0
        confidence = _album_confidence(
            wanted_album=album,
            wanted_artist=artist,
            expected_track_count=expected_track_count,
            album=actual_album,
            artist=actual_artist,
            track_count=track_count,
        )

        results.append(
            DeezerAlbumCandidate(
                album_id=album_id,
                album=actual_album,
                artist=actual_artist,
                track_count=track_count,
                confidence=confidence,
            )
        )

    ordered = sorted(
        results,
        key=lambda candidate: (
            -candidate.confidence,
            candidate.album.casefold(),
        ),
    )
    logger.info(
        "Deezer-Albumsuche | Album=%r | Treffer=%d | Bester=%s",
        album,
        len(ordered),
        (
            f"{ordered[0].album_id}:{ordered[0].album}:{ordered[0].confidence}"
            if ordered
            else "kein Treffer"
        ),
    )

    return ordered


def lookup_album(album_id: str):
    """Lädt die vollständige Deezer-Albumtrackliste als DirectAlbumResult."""
    # Lokaler Import bricht eine mögliche Importschleife und hält die
    # Provider-Schicht schlank.
    from ..direct_album_lookup import DirectAlbumResult, DirectAlbumTrack

    album_payload = _get_json(f"{DEEZER_API}/album/{album_id}")

    album_name = str(album_payload.get("title") or "")
    album_artist = str((album_payload.get("artist") or {}).get("name") or "")
    label = str(album_payload.get("label") or "")
    year = _year(str(album_payload.get("release_date") or ""))
    genres = album_payload.get("genres") or {}
    genre = ""
    genre_data = genres.get("data") if isinstance(genres, dict) else None

    if genre_data:
        genre = str((genre_data[0] or {}).get("name") or "")

    track_payload = _get_json(f"{DEEZER_API}/album/{album_id}/tracks?limit=300")
    raw_tracks = track_payload.get("data", []) or []
    total_tracks = str(len(raw_tracks))
    disc_numbers = {
        _optional_int(track.get("disk_number")) or 1 for track in raw_tracks
    }
    total_discs = str(len(disc_numbers)) if disc_numbers else ""

    tracks = tuple(
        DirectAlbumTrack(
            title=str(track.get("title") or ""),
            artist=str((track.get("artist") or {}).get("name") or ""),
            album_artist=album_artist,
            album=album_name,
            genre=genre,
            year=year,
            track=_number(track.get("track_position")),
            total_tracks=total_tracks,
            disc=_number(track.get("disk_number")),
            total_discs=total_discs,
            isrc=str(track.get("isrc") or ""),
            label=label,
            duration_ms=_duration_ms(track.get("duration")),
            external_id=str(track.get("id") or ""),
            preview_url=str(track.get("preview") or ""),
        )
        for track in raw_tracks
    )

    if not tracks:
        raise DeezerProviderError(
            "Deezer lieferte für diese Album-ID keine Trackliste."
        )

    return DirectAlbumResult(
        provider="deezer",
        album=album_name,
        album_artist=album_artist,
        tracks=tracks,
    )


def search_song(
    title: str,
    artist: str = "",
    album: str = "",
    *,
    limit: int = 25,
):
    """Sucht einen einzelnen Titel über die Deezer-API (Fallback-Pfad).

    Liefert MetadataCandidate-Objekte. ISRC ist in Suchtreffern nicht
    enthalten; für vollständige Tracklisten inkl. ISRC dient lookup_album().
    """
    from ..models.metadata import MetadataCandidate

    terms = [part.strip() for part in (artist, title) if part.strip()]

    if not terms:
        return []

    url = f"{DEEZER_API}/search?" + urlencode(
        {"q": " ".join(terms), "limit": max(1, min(limit, 50))}
    )

    try:
        payload = _get_json(url)
    except DeezerProviderError:
        return []

    results = []

    for item in payload.get("data", []) or []:
        actual_title = str(item.get("title") or "")
        actual_artist = str((item.get("artist") or {}).get("name") or "")
        actual_album = str((item.get("album") or {}).get("title") or "")
        score = _field_score(title, actual_title, exact=70, contains=45)
        score += _field_score(artist, actual_artist, exact=20, contains=11)
        score += _field_score(album, actual_album, exact=15, contains=8)

        results.append(
            MetadataCandidate(
                source="deezer",
                confidence=max(0, min(100, score)),
                title=actual_title,
                artist=actual_artist,
                album_artist=actual_artist,
                album=actual_album,
                duration_ms=_duration_ms(item.get("duration")),
                external_id=str(item.get("id") or ""),
                release_id=str((item.get("album") or {}).get("id") or ""),
            )
        )

    return sorted(results, key=lambda candidate: -candidate.confidence)


def lookup_track_by_isrc(isrc: str):
    """Sucht einen Track exakt über seine ISRC (``/track/isrc:{isrc}``).

    Liefert einen MetadataCandidate oder ``None``. Zusätzlich wird – wenn
    möglich – das Album für Label/Genre/Jahr nachgeladen.
    """
    from ..models.metadata import MetadataCandidate

    isrc = (isrc or "").strip().upper()
    if not isrc:
        return None

    try:
        track = _get_json(f"{DEEZER_API}/track/isrc:{isrc}")
    except DeezerProviderError:
        return None
    if not isinstance(track, dict) or not track.get("id"):
        return None

    album_ref = track.get("album") or {}
    album_id = str(album_ref.get("id") or "")
    label = ""
    genre = ""
    year = _year_from_date(str(track.get("release_date") or ""))

    if album_id:
        try:
            album = _get_json(f"{DEEZER_API}/album/{album_id}")
        except DeezerProviderError:
            album = {}
        if isinstance(album, dict):
            label = str(album.get("label") or "")
            genres = (album.get("genres") or {}).get("data") or []
            if genres:
                genre = str((genres[0] or {}).get("name") or "")
            year = year or _year_from_date(str(album.get("release_date") or ""))

    artist = str((track.get("artist") or {}).get("name") or "")
    return MetadataCandidate(
        source="deezer",
        confidence=95,  # exakter ISRC-Treffer
        title=str(track.get("title") or ""),
        artist=artist,
        album_artist=artist,
        album=str(album_ref.get("title") or ""),
        genre=genre,
        year=year,
        label=label,
        isrc=isrc,
        duration_ms=_duration_ms(track.get("duration")),
        external_id=str(track.get("id") or ""),
        release_id=album_id,
    )


def _year_from_date(value: str) -> str:
    value = (value or "").strip()
    return value[:4] if len(value) >= 4 and value[:4].isdigit() else ""


def _album_confidence(
    *,
    wanted_album: str,
    wanted_artist: str,
    expected_track_count: int | None,
    album: str,
    artist: str,
    track_count: int,
) -> int:
    from .streaming_catalog import loose_album_key

    # Editions-/Artikel-toleranter Titel-Abgleich (global, s. streaming_catalog):
    # „Die Passion Whisky" == „Passion Whisky (Premium Edition)".
    loose_match = bool(
        loose_album_key(wanted_album)
        and loose_album_key(wanted_album) == loose_album_key(album)
    )
    if loose_match:
        score = 60
    else:
        score = _field_score(wanted_album, album, exact=65, contains=38)
    score += _field_score(wanted_artist, artist, exact=25, contains=14)

    if expected_track_count is not None and track_count > 0:
        difference = abs(expected_track_count - track_count)
        if difference == 0:
            score += 15
        elif loose_match:
            # Gleiches Album, andere Edition -> Trackzahl darf abweichen,
            # nur milde dämpfen statt hart bestrafen.
            score -= min(6, difference)
        else:
            score -= min(18, difference * 3)

    return max(0, min(100, score))


def _field_score(wanted: str, actual: str, *, exact: int, contains: int) -> int:
    wanted_n = _normalize(wanted)
    actual_n = _normalize(actual)

    if not wanted_n:
        return 0

    if wanted_n == actual_n:
        return exact

    if wanted_n in actual_n or actual_n in wanted_n:
        return contains

    wanted_words = set(wanted_n.split())
    actual_words = set(actual_n.split())

    if not wanted_words or not actual_words:
        return 0

    return round(
        contains
        * len(wanted_words & actual_words)
        / max(len(wanted_words), len(actual_words))
    )


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _year(value: str) -> str:
    match = re.match(r"^(\d{4})", value)
    return match.group(1) if match else ""


def _number(value: object) -> str:
    parsed = _optional_int(value)
    return str(parsed) if parsed is not None else ""


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _duration_ms(value: object) -> int | None:
    seconds = _optional_int(value)
    return seconds * 1000 if seconds is not None else None
