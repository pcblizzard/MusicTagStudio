from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, replace
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..models.metadata import MetadataCandidate
from ..musicbrainz_http import (
    MUSICBRAINZ_BASE_URL,
    MUSICBRAINZ_USER_AGENT,
    wait_for_musicbrainz_slot,
)
from . import http_cache


BASE_URL = MUSICBRAINZ_BASE_URL
USER_AGENT = MUSICBRAINZ_USER_AGENT
TIMEOUT_SECONDS = 12


class MusicBrainzProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class MusicBrainzReleaseCandidate:
    release_id: str
    album: str
    artist: str
    track_count: int
    year: str
    status: str
    country: str
    confidence: int


def search_release(
    album: str,
    artist: str = "",
    *,
    expected_track_count: int | None = None,
    wanted_year: str = "",
    limit: int = 25,
) -> list[MusicBrainzReleaseCandidate]:
    query_parts = [
        f'release:"{_escape(album)}"'
    ]

    if artist.strip():
        query_parts.append(
            f'artist:"{_escape(artist)}"'
        )

    params = {
        "query": " AND ".join(query_parts),
        "fmt": "json",
        "limit": max(1, min(limit, 100)),
    }
    payload = _request_json(
        f"{BASE_URL}/release?{urlencode(params)}"
    )
    results: list[
        MusicBrainzReleaseCandidate
    ] = []

    for release in payload.get(
        "releases",
        [],
    ):
        release_id = str(
            release.get("id", "")
        )

        if not release_id:
            continue

        actual_album = str(
            release.get("title", "")
        )
        actual_artist = _artist_credit(
            release.get(
                "artist-credit",
                [],
            )
        )
        track_count = (
            _optional_int(
                release.get(
                    "track-count"
                )
            )
            or 0
        )
        year = _year(
            str(release.get("date", ""))
        )
        status = str(
            release.get("status", "")
        )
        search_score = (
            _optional_int(
                release.get("score")
            )
            or 0
        )
        confidence = _release_match_score(
            wanted_album=album,
            wanted_artist=artist,
            expected_track_count=(
                expected_track_count
            ),
            wanted_year=wanted_year,
            album=actual_album,
            artist=actual_artist,
            track_count=track_count,
            year=year,
            status=status,
            search_score=search_score,
        )

        results.append(
            MusicBrainzReleaseCandidate(
                release_id=release_id,
                album=actual_album,
                artist=actual_artist,
                track_count=track_count,
                year=year,
                status=status,
                country=str(
                    release.get(
                        "country",
                        "",
                    )
                ),
                confidence=confidence,
            )
        )

    return sorted(
        results,
        key=lambda item: (
            -item.confidence,
            abs(
                (
                    expected_track_count
                    or item.track_count
                )
                - item.track_count
            ),
            item.year or "9999",
        ),
    )


def _release_match_score(
    *,
    wanted_album: str,
    wanted_artist: str,
    expected_track_count: int | None,
    wanted_year: str,
    album: str,
    artist: str,
    track_count: int,
    year: str,
    status: str,
    search_score: int,
) -> int:
    score = _text_match_score(
        wanted_album,
        album,
        exact=55,
        contains=32,
    )
    score += _text_match_score(
        wanted_artist,
        artist,
        exact=22,
        contains=12,
    )

    if (
        expected_track_count is not None
        and track_count > 0
    ):
        difference = abs(
            expected_track_count
            - track_count
        )

        if difference == 0:
            score += 18
        else:
            score -= min(
                24,
                difference * 4,
            )

    if wanted_year and year:
        if wanted_year == year:
            score += 5
        else:
            score -= 2

    if status.casefold() == "official":
        score += 5

    score += round(
        max(0, min(100, search_score))
        / 20
    )

    return max(0, min(100, score))


def _text_match_score(
    wanted: str,
    actual: str,
    *,
    exact: int,
    contains: int,
) -> int:
    wanted_n = _normalize_text(wanted)
    actual_n = _normalize_text(actual)

    if not wanted_n:
        return 0

    if wanted_n == actual_n:
        return exact

    if (
        wanted_n in actual_n
        or actual_n in wanted_n
    ):
        return contains

    wanted_words = set(wanted_n.split())
    actual_words = set(actual_n.split())

    if not wanted_words or not actual_words:
        return 0

    return round(
        contains
        * len(wanted_words & actual_words)
        / max(
            len(wanted_words),
            len(actual_words),
        )
    )


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize(
        "NFKD",
        value.casefold(),
    )
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(
            character
        )
    )
    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(value.split())


def search_song(
    title: str,
    artist: str = "",
    album: str = "",
    *,
    limit: int = 10,
) -> list[MetadataCandidate]:
    query_parts = [f'recording:"{_escape(title)}"']
    if artist.strip():
        query_parts.append(f'artist:"{_escape(artist)}"')
    if album.strip():
        query_parts.append(f'release:"{_escape(album)}"')
    params = {
        "query": " AND ".join(query_parts),
        "fmt": "json",
        "limit": max(1, min(limit, 100)),
    }
    payload = _request_json(f"{BASE_URL}/recording?{urlencode(params)}")
    results: list[MetadataCandidate] = []
    for recording in payload.get("recordings", []):
        results.append(_candidate_from_recording(recording))
    return sorted(results, key=lambda item: -item.confidence)


def lookup_recording_by_id(recording_id: str) -> MetadataCandidate | None:
    """Lädt ein Recording per MBID (z. B. aus einem AcoustID-Treffer)."""
    recording_id = recording_id.strip()

    if not recording_id:
        return None

    params = {
        "fmt": "json",
        "inc": "artists+releases+isrcs+genres+tags+media",
    }
    payload = _request_json(
        f"{BASE_URL}/recording/{recording_id}?{urlencode(params)}"
    )

    if not payload.get("id"):
        return None

    return _candidate_from_recording(payload)


def lookup_recording_by_isrc(isrc: str) -> MetadataCandidate | None:
    """Sucht ein Recording exakt über seine ISRC (statt unsicherer Textsuche).

    Nutzt den ISRC-Endpunkt ``/ws/2/isrc/{isrc}``; nimmt das Recording mit dem
    höchsten Score. Gibt ``None`` zurück, wenn nichts gefunden wird.
    """
    isrc = (isrc or "").strip().upper()
    if not isrc:
        return None

    params = {
        "fmt": "json",
        "inc": "artists+releases+isrcs+genres+tags+media",
    }
    try:
        payload = _request_json(f"{BASE_URL}/isrc/{isrc}?{urlencode(params)}")
    except MusicBrainzProviderError:
        # z. B. HTTP 404: ISRC bei MusicBrainz unbekannt -> kein Treffer.
        return None

    recordings = payload.get("recordings") or []
    if not recordings:
        return None

    best = max(recordings, key=lambda item: int(item.get("score") or 0))
    candidate = _candidate_from_recording(best)
    # ISRC sicher setzen (der Endpunkt liefert sie evtl. nicht pro Recording).
    if not candidate.isrc:
        candidate = replace(candidate, isrc=isrc)
    return candidate


def _candidate_from_recording(recording: dict) -> MetadataCandidate:
    releases = recording.get("releases") or []
    release = releases[0] if releases else {}
    media = release.get("media") or []
    medium = media[0] if media else {}
    track_data = _find_track(medium, recording.get("id"))
    isrcs = recording.get("isrcs") or []
    tags = recording.get("tags") or []
    genres = recording.get("genres") or []
    label = _extract_label(release)
    genre = _best_tag(genres or tags)
    artist = _artist_credit(recording.get("artist-credit") or [])
    album_artist = _artist_credit(release.get("artist-credit") or []) or artist
    track_number = str(track_data.get("number") or track_data.get("position") or "")
    total_tracks = str(medium.get("track-count") or "")
    disc_number = str(medium.get("position") or "")
    total_discs = str(len(media) or "") if media else ""
    score = int(recording.get("score") or 0)
    return MetadataCandidate(
        source="musicbrainz",
        confidence=score,
        title=str(recording.get("title", "")),
        artist=artist,
        album_artist=album_artist,
        album=str(release.get("title", "")),
        genre=genre,
        year=_year(str(release.get("date", ""))),
        track=track_number,
        total_tracks=total_tracks,
        disc=disc_number,
        total_discs=total_discs,
        isrc=str(isrcs[0]) if isrcs else "",
        label=label,
        duration_ms=_optional_int(recording.get("length")),
        external_id=str(recording.get("id", "")),
        release_id=str(release.get("id", "")),
    )


def _request_json(url: str) -> dict:
    cached = http_cache.load(url)
    if cached is not None:
        return cached

    wait_for_musicbrainz_slot()
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = json.load(response)
    except HTTPError as error:
        raise MusicBrainzProviderError(
            f"MusicBrainz antwortete mit HTTP-Fehler {error.code}."
        ) from error
    except URLError as error:
        raise MusicBrainzProviderError(
            f"Keine Verbindung zu MusicBrainz: {error.reason}"
        ) from error
    except (TimeoutError, json.JSONDecodeError) as error:
        raise MusicBrainzProviderError(
            "Die MusicBrainz-Antwort konnte nicht verarbeitet werden."
        ) from error
    http_cache.store(url, data)
    return data


def _artist_credit(credits: list[dict]) -> str:
    pieces: list[str] = []
    for credit in credits:
        name = str(credit.get("name") or credit.get("artist", {}).get("name") or "")
        if name:
            pieces.append(name)
        joinphrase = str(credit.get("joinphrase") or "")
        if joinphrase:
            pieces.append(joinphrase)
    return "".join(pieces).strip()


def _find_track(medium: dict, recording_id: str | None) -> dict:
    for track in medium.get("tracks") or []:
        linked = track.get("recording") or {}
        if not recording_id or linked.get("id") == recording_id:
            return track
    return {}


def _extract_label(release: dict) -> str:
    labels: list[str] = []
    for info in release.get("label-info") or []:
        name = str((info.get("label") or {}).get("name") or "")
        if name and name not in labels:
            labels.append(name)
    return ", ".join(labels)


def _best_tag(tags: list[dict]) -> str:
    if not tags:
        return ""
    sorted_tags = sorted(
        tags,
        key=lambda item: _optional_int(item.get("count")) or 0,
        reverse=True,
    )
    return str(sorted_tags[0].get("name") or "")


def _year(value: str) -> str:
    match = re.match(r"^(\d{4})", value)
    return match.group(1) if match else ""


def _escape(value: str) -> str:
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/])', r"\\\1", value.strip())


def _optional_int(value: object) -> int | None:
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
