from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..normalizers import move_feature_artists


SEARCH_ENDPOINT = "https://itunes.apple.com/search"
DEFAULT_COUNTRY = "DE"
DEFAULT_LIMIT = 50
REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class AppleMusicResult:
    title: str = ""
    artist: str = ""
    album_artist: str = ""
    album: str = ""
    genre: str = ""
    release_date: str = ""
    year: str = ""

    track: str = ""
    total_tracks: str = ""
    disc: str = ""
    total_discs: str = ""

    duration_ms: int | None = None
    track_id: int | None = None
    collection_id: int | None = None
    track_url: str = ""
    artwork_url: str = ""

    score: int = 0

    @property
    def duration_text(self) -> str:
        if self.duration_ms is None:
            return ""

        seconds = max(0, self.duration_ms // 1000)
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes}:{seconds:02d}"


class AppleMusicProviderError(RuntimeError):
    """Fehler beim Abrufen oder Verarbeiten von Apple-Music-Daten."""


def search_song(
    title: str,
    artist: str = "",
    album: str = "",
    *,
    country: str = DEFAULT_COUNTRY,
    limit: int = DEFAULT_LIMIT,
) -> list[AppleMusicResult]:
    """
    Sucht kostenfrei über die öffentliche iTunes Search API.

    Die Ergebnisse werden lokal nach Titel, Künstler und Album bewertet.
    Feature-Nennungen im Titel werden nach den MusicTagStudio-Regeln
    in das Künstlerfeld verschoben. Es werden keine Tags geschrieben.
    """
    search_parts = [
        part.strip()
        for part in (artist, album, title)
        if part.strip()
    ]

    if not search_parts:
        return []

    parameters = {
        "term": " ".join(search_parts),
        "country": country.upper(),
        "media": "music",
        "entity": "song",
        "limit": max(1, min(limit, 200)),
        "lang": "de_de",
        "version": 2,
    }

    request_url = f"{SEARCH_ENDPOINT}?{urlencode(parameters)}"
    request = Request(
        request_url,
        headers={
            "User-Agent": "MusicTagStudio/0.1",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise AppleMusicProviderError(
            f"Apple antwortete mit HTTP-Fehler {error.code}."
        ) from error
    except URLError as error:
        raise AppleMusicProviderError(
            f"Keine Verbindung zur Apple-Suche: {error.reason}"
        ) from error
    except (TimeoutError, json.JSONDecodeError) as error:
        raise AppleMusicProviderError(
            "Die Antwort der Apple-Suche konnte nicht verarbeitet werden."
        ) from error

    raw_results = payload.get("results", [])

    results = [
        _result_from_payload(
            item,
            wanted_title=title,
            wanted_artist=artist,
            wanted_album=album,
        )
        for item in raw_results
        if item.get("wrapperType") == "track"
        and item.get("kind") == "song"
    ]

    return sorted(
        results,
        key=lambda result: (
            -result.score,
            _number_or_large(result.disc),
            _number_or_large(result.track),
            result.title.casefold(),
        ),
    )


def _result_from_payload(
    item: dict,
    *,
    wanted_title: str,
    wanted_artist: str,
    wanted_album: str,
) -> AppleMusicResult:
    release_date = str(item.get("releaseDate", ""))
    year = _extract_year(release_date)

    raw_title = str(item.get("trackName", ""))
    raw_artist = str(item.get("artistName", ""))

    title, artist = move_feature_artists(
        raw_title,
        raw_artist,
    )

    album = str(item.get("collectionName", ""))
    album_artist = str(
        item.get("collectionArtistName")
        or item.get("artistName")
        or ""
    )

    score = _match_score(
        wanted_title=wanted_title,
        wanted_artist=wanted_artist,
        wanted_album=wanted_album,
        title=title,
        artist=artist,
        album=album,
    )

    duration_value = item.get("trackTimeMillis")
    duration_ms = (
        int(duration_value)
        if isinstance(duration_value, (int, float))
        else None
    )

    return AppleMusicResult(
        title=title,
        artist=artist,
        album_artist=album_artist,
        album=album,
        genre=str(item.get("primaryGenreName", "")),
        release_date=release_date,
        year=year,
        track=_string_number(item.get("trackNumber")),
        total_tracks=_string_number(item.get("trackCount")),
        disc=_string_number(item.get("discNumber")),
        total_discs=_string_number(item.get("discCount")),
        duration_ms=duration_ms,
        track_id=_optional_int(item.get("trackId")),
        collection_id=_optional_int(item.get("collectionId")),
        track_url=str(item.get("trackViewUrl", "")),
        artwork_url=str(item.get("artworkUrl100", "")),
        score=score,
    )


def _match_score(
    *,
    wanted_title: str,
    wanted_artist: str,
    wanted_album: str,
    title: str,
    artist: str,
    album: str,
) -> int:
    score = 0
    score += _field_score(
        wanted_title,
        title,
        exact=55,
        contains=30,
    )
    score += _field_score(
        wanted_artist,
        artist,
        exact=25,
        contains=14,
    )
    score += _field_score(
        wanted_album,
        album,
        exact=20,
        contains=12,
    )
    return score


def _field_score(
    wanted: str,
    actual: str,
    *,
    exact: int,
    contains: int,
) -> int:
    wanted_normalized = _normalize(wanted)
    actual_normalized = _normalize(actual)

    if not wanted_normalized:
        return 0

    if wanted_normalized == actual_normalized:
        return exact

    if (
        wanted_normalized in actual_normalized
        or actual_normalized in wanted_normalized
    ):
        return contains

    wanted_words = set(wanted_normalized.split())
    actual_words = set(actual_normalized.split())

    if not wanted_words or not actual_words:
        return 0

    overlap = len(wanted_words & actual_words)

    return round(
        contains
        * overlap
        / max(len(wanted_words), len(actual_words))
    )


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _extract_year(value: str) -> str:
    if not value:
        return ""

    try:
        normalized_value = value.replace("Z", "+00:00")
        return str(datetime.fromisoformat(normalized_value).year)
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


def _number_or_large(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 999_999
