from __future__ import annotations

import json
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..models.metadata import MetadataCandidate


BASE_URL = "https://musicbrainz.org/ws/2"
USER_AGENT = "MusicTagStudio/0.3.0 (https://github.com/pcblizzard/MusicTagStudio)"
TIMEOUT_SECONDS = 20
_MIN_REQUEST_INTERVAL = 1.05
_request_lock = threading.Lock()
_last_request_time = 0.0


class MusicBrainzProviderError(RuntimeError):
    pass


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
    global _last_request_time
    with _request_lock:
        wait = _MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_time)
        if wait > 0:
            time.sleep(wait)
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
        finally:
            _last_request_time = time.monotonic()
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
    sorted_tags = sorted(tags, key=lambda item: int(item.get("count") or 0), reverse=True)
    return str(sorted_tags[0].get("name") or "")


def _year(value: str) -> str:
    match = re.match(r"^(\d{4})", value)
    return match.group(1) if match else ""


def _escape(value: str) -> str:
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/])', r"\\\1", value.strip())


def _optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
