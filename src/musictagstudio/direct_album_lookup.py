from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .direct_references import DirectAlbumReference
from .models.metadata import MetadataCandidate
from .models.song import Song


USER_AGENT = (
    "MusicTagStudio/0.6.1 "
    "(https://github.com/pcblizzard/MusicTagStudio)"
)
TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class DirectAlbumTrack:
    title: str
    artist: str
    album_artist: str
    album: str
    genre: str
    year: str
    track: str
    total_tracks: str
    disc: str
    total_discs: str
    isrc: str = ""
    label: str = ""
    copyright: str = ""
    composer: str = ""
    duration_ms: int | None = None

    def as_candidate(
        self,
        source: str,
    ) -> MetadataCandidate:
        return MetadataCandidate(
            source=source,
            confidence=100,
            title=self.title,
            artist=self.artist,
            album_artist=self.album_artist,
            album=self.album,
            genre=self.genre,
            year=self.year,
            track=self.track,
            total_tracks=self.total_tracks,
            disc=self.disc,
            total_discs=self.total_discs,
            isrc=self.isrc,
            label=self.label,
            copyright=self.copyright,
            composer=self.composer,
        )


@dataclass(frozen=True)
class DirectAlbumResult:
    provider: str
    album: str
    album_artist: str
    tracks: tuple[DirectAlbumTrack, ...]


class DirectAlbumLookupError(RuntimeError):
    """Ein Album konnte über die direkte Anbieter-ID nicht geladen werden."""


def lookup_album(
    reference: DirectAlbumReference,
    *,
    apple_country: str = "DE",
) -> DirectAlbumResult:
    if reference.provider == "apple_music":
        return _lookup_apple_album(
            reference.reference_id,
            country=apple_country,
        )

    if reference.provider == "musicbrainz":
        release_id = reference.reference_id

        if reference.reference_type == "release-group":
            release_id = _resolve_release_group(
                reference.reference_id
            )

        return _lookup_musicbrainz_release(
            release_id
        )

    raise DirectAlbumLookupError(
        "Diese direkte Albumquelle wird derzeit nicht unterstützt."
    )


def match_album_tracks(
    songs: list[Song],
    album: DirectAlbumResult,
) -> dict[int, DirectAlbumTrack]:
    """
    Ordnet lokale Dateien den Tracks des direkt geladenen Albums zu.

    Priorität:
    1. Disc- und Tracknummer
    2. normalisierter Titel
    """
    matches: dict[int, DirectAlbumTrack] = {}
    used_track_indexes: set[int] = set()

    for song_index, song in enumerate(songs):
        song_track = _as_int(song.track)
        song_disc = _as_int(song.disc) or 1

        if song_track is None:
            continue

        for track_index, track in enumerate(album.tracks):
            if track_index in used_track_indexes:
                continue

            if (
                _as_int(track.track) == song_track
                and (_as_int(track.disc) or 1) == song_disc
            ):
                matches[song_index] = track
                used_track_indexes.add(track_index)
                break

    for song_index, song in enumerate(songs):
        if song_index in matches:
            continue

        normalized_title = _normalize(song.title)

        if not normalized_title:
            continue

        candidates = [
            (track_index, track)
            for track_index, track in enumerate(album.tracks)
            if track_index not in used_track_indexes
            and _normalize(track.title) == normalized_title
        ]

        if len(candidates) == 1:
            track_index, track = candidates[0]
            matches[song_index] = track
            used_track_indexes.add(track_index)

    return matches


def _lookup_apple_album(
    album_id: str,
    *,
    country: str,
) -> DirectAlbumResult:
    payload = _get_json(
        "https://itunes.apple.com/lookup?"
        + urlencode(
            {
                "id": album_id,
                "entity": "song",
                "country": country,
                "lang": "de_de",
            }
        )
    )

    results = payload.get("results", [])

    collection = next(
        (
            item
            for item in results
            if item.get("wrapperType") == "collection"
        ),
        None,
    )

    track_items = [
        item
        for item in results
        if item.get("wrapperType") == "track"
        and item.get("kind") == "song"
    ]

    if not collection or not track_items:
        raise DirectAlbumLookupError(
            "Apple Music lieferte für diese Album-ID keine Trackliste."
        )

    album_name = str(
        collection.get("collectionName", "")
    )
    album_artist = str(
        collection.get("artistName", "")
    )
    copyright_value = str(
        collection.get("copyright", "")
    )

    tracks = tuple(
        DirectAlbumTrack(
            title=str(item.get("trackName", "")),
            artist=str(item.get("artistName", "")),
            album_artist=album_artist,
            album=album_name,
            genre=str(item.get("primaryGenreName", "")),
            year=_year(
                str(item.get("releaseDate", ""))
            ),
            track=_number(item.get("trackNumber")),
            total_tracks=_number(item.get("trackCount")),
            disc=_number(item.get("discNumber")),
            total_discs=_number(item.get("discCount")),
            copyright=copyright_value,
            duration_ms=_optional_int(
                item.get("trackTimeMillis")
            ),
        )
        for item in track_items
    )

    return DirectAlbumResult(
        provider="apple_music",
        album=album_name,
        album_artist=album_artist,
        tracks=tracks,
    )


def _resolve_release_group(
    release_group_id: str,
) -> str:
    payload = _get_json(
        "https://musicbrainz.org/ws/2/release?"
        + urlencode(
            {
                "release-group": release_group_id,
                "fmt": "json",
                "limit": 100,
            }
        )
    )

    releases = payload.get("releases", [])

    if not releases:
        raise DirectAlbumLookupError(
            "Die MusicBrainz Release Group enthält keine Releases."
        )

    # Offiziell gelistete Veröffentlichung bevorzugen.
    releases.sort(
        key=lambda release: (
            release.get("status") != "Official",
            not bool(release.get("date")),
            str(release.get("date", "")),
        )
    )

    release_id = str(
        releases[0].get("id", "")
    )

    if not release_id:
        raise DirectAlbumLookupError(
            "Für die MusicBrainz Release Group konnte "
            "kein Release bestimmt werden."
        )

    return release_id


def _lookup_musicbrainz_release(
    release_id: str,
) -> DirectAlbumResult:
    payload = _get_json(
        "https://musicbrainz.org/ws/2/release/"
        f"{release_id}?"
        + urlencode(
            {
                "inc": (
                    "recordings+artist-credits+labels+"
                    "release-groups+media+isrcs"
                ),
                "fmt": "json",
            }
        )
    )

    album_name = str(payload.get("title", ""))
    album_artist = _artist_credit(
        payload.get("artist-credit", [])
    )
    year = _year(str(payload.get("date", "")))

    label = ""

    label_info = payload.get("label-info", [])

    if label_info:
        label = str(
            (label_info[0].get("label") or {}).get(
                "name",
                "",
            )
        )

    media = payload.get("media", [])
    total_discs = str(len(media)) if media else ""
    tracks: list[DirectAlbumTrack] = []

    for medium_index, medium in enumerate(
        media,
        start=1,
    ):
        medium_tracks = medium.get("tracks", [])
        total_tracks = str(len(medium_tracks))

        for track in medium_tracks:
            recording = track.get("recording") or {}
            isrcs = recording.get("isrcs") or []

            tracks.append(
                DirectAlbumTrack(
                    title=str(
                        recording.get("title")
                        or track.get("title")
                        or ""
                    ),
                    artist=_artist_credit(
                        recording.get(
                            "artist-credit",
                            [],
                        )
                    )
                    or album_artist,
                    album_artist=album_artist,
                    album=album_name,
                    genre="",
                    year=year,
                    track=_number(
                        track.get("position")
                        or track.get("number")
                    ),
                    total_tracks=total_tracks,
                    disc=str(medium_index),
                    total_discs=total_discs,
                    isrc=str(isrcs[0]) if isrcs else "",
                    label=label,
                )
            )

    if not tracks:
        raise DirectAlbumLookupError(
            "MusicBrainz lieferte für dieses Release keine Trackliste."
        )

    return DirectAlbumResult(
        provider="musicbrainz",
        album=album_name,
        album_artist=album_artist,
        tracks=tuple(tracks),
    )


def _get_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:
            return json.load(response)
    except (
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as error:
        raise DirectAlbumLookupError(
            f"Die direkte Albumabfrage ist fehlgeschlagen: {error}"
        ) from error


def _artist_credit(value: list[dict]) -> str:
    names = [
        str(
            (credit.get("artist") or {}).get(
                "name",
                credit.get("name", ""),
            )
        )
        for credit in value
    ]

    return ", ".join(
        name
        for name in names
        if name
    )


def _normalize(value: str) -> str:
    value = unicodedata.normalize(
        "NFKD",
        value.casefold(),
    )
    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )
    value = re.sub(
        r"\b(?:feat(?:uring)?|ft)\.?\b.*$",
        "",
        value,
    )
    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )
    return " ".join(value.split())


def _year(value: str) -> str:
    match = re.match(r"^(\d{4})", value)
    return match.group(1) if match else ""


def _number(value: object) -> str:
    if value in (None, ""):
        return ""

    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _optional_int(
    value: object,
) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_int(
    value: str,
) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
