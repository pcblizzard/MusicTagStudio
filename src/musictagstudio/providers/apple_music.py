from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..models.metadata import MetadataCandidate


SEARCH_ENDPOINT = "https://itunes.apple.com/search"
DEFAULT_COUNTRY = "DE"
DEFAULT_LIMIT = 50
REQUEST_TIMEOUT_SECONDS = 15


class AppleMusicProviderError(RuntimeError):
    pass


def search_song(
    title: str,
    artist: str = "",
    album: str = "",
    *,
    country: str = DEFAULT_COUNTRY,
    limit: int = DEFAULT_LIMIT,
) -> list[MetadataCandidate]:
    terms = [part.strip() for part in (artist, album, title) if part.strip()]
    if not terms:
        return []

    params = {
        "term": " ".join(terms),
        "country": country.upper(),
        "media": "music",
        "entity": "song",
        "limit": max(1, min(limit, 200)),
        "lang": "de_de",
        "version": 2,
    }
    request = Request(
        f"{SEARCH_ENDPOINT}?{urlencode(params)}",
        headers={"User-Agent": "MusicTagStudio/0.3.0", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise AppleMusicProviderError(f"Apple antwortete mit HTTP-Fehler {error.code}.") from error
    except URLError as error:
        raise AppleMusicProviderError(f"Keine Verbindung zur Apple-Suche: {error.reason}") from error
    except (TimeoutError, json.JSONDecodeError) as error:
        raise AppleMusicProviderError("Die Apple-Antwort konnte nicht verarbeitet werden.") from error

    results: list[MetadataCandidate] = []
    for item in payload.get("results", []):
        if item.get("wrapperType") != "track" or item.get("kind") != "song":
            continue
        candidate = _candidate_from_item(item, title, artist, album)
        results.append(candidate)
    return sorted(results, key=lambda item: (-item.confidence, item.disc, item.track))


def _candidate_from_item(
    item: dict,
    wanted_title: str,
    wanted_artist: str,
    wanted_album: str,
) -> MetadataCandidate:
    title = str(item.get("trackName", ""))
    artist = str(item.get("artistName", ""))
    album = str(item.get("collectionName", ""))
    release_date = str(item.get("releaseDate", ""))
    score = _match_score(wanted_title, wanted_artist, wanted_album, title, artist, album)
    return MetadataCandidate(
        source="apple_music",
        confidence=score,
        title=title,
        artist=artist,
        album_artist=str(item.get("collectionArtistName") or artist),
        album=album,
        genre=str(item.get("primaryGenreName", "")),
        year=_extract_year(release_date),
        track=_string_number(item.get("trackNumber")),
        total_tracks=_string_number(item.get("trackCount")),
        disc=_string_number(item.get("discNumber")),
        total_discs=_string_number(item.get("discCount")),
        duration_ms=_optional_int(item.get("trackTimeMillis")),
        external_id=str(item.get("trackId", "")),
        release_id=str(item.get("collectionId", "")),
    )


def _match_score(wt: str, wa: str, wal: str, title: str, artist: str, album: str) -> int:
    return min(
        100,
        _field_score(wt, title, 55, 30)
        + _field_score(wa, artist, 25, 14)
        + _field_score(wal, album, 20, 12),
    )


def _field_score(wanted: str, actual: str, exact: int, contains: int) -> int:
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
    return round(contains * len(wanted_words & actual_words) / max(len(wanted_words), len(actual_words)))


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _extract_year(value: str) -> str:
    if not value:
        return ""
    try:
        return str(datetime.fromisoformat(value.replace("Z", "+00:00")).year)
    except ValueError:
        match = re.match(r"^(\d{4})", value)
        return match.group(1) if match else ""


def _string_number(value: object) -> str:
    if value in (None, ""):
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
