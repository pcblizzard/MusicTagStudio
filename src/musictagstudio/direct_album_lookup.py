from __future__ import annotations

import json
import re
import unicodedata
import threading
import time
from functools import lru_cache
from pathlib import Path

from mutagen import File as MutagenFile
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .direct_references import DirectAlbumReference
from .models.metadata import MetadataCandidate
from .models.song import Song


USER_AGENT = (
    "MusicTagStudio/0.6.7.7 "
    "(https://github.com/pcblizzard/MusicTagStudio)"
)
TIMEOUT_SECONDS = 20
_MB_REQUEST_INTERVAL = 1.05
_mb_request_lock = threading.Lock()
_mb_last_request_time = 0.0


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
    external_id: str = ""

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
            duration_ms=self.duration_ms,
            external_id=self.external_id,
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
        if reference.reference_type == "song":
            return _lookup_apple_song(
                reference.reference_id,
                country=apple_country,
            )

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


@dataclass(frozen=True)
class AlbumTrackMatch:
    local_index: int
    track_index: int
    track: DirectAlbumTrack
    score: int
    confidence: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AlbumMatchingResult:
    matches: tuple[AlbumTrackMatch, ...]
    unmatched_local_indexes: tuple[int, ...]
    unused_track_indexes: tuple[int, ...]
    ambiguous_local_indexes: tuple[int, ...]

    @property
    def mapping(
        self,
    ) -> dict[int, DirectAlbumTrack]:
        return {
            match.local_index: match.track
            for match in self.matches
        }

    @property
    def complete(self) -> bool:
        return (
            not self.unmatched_local_indexes
            and not self.unused_track_indexes
            and not self.ambiguous_local_indexes
        )


def match_album_tracks(
    songs: list[Song],
    album: DirectAlbumResult,
) -> dict[int, DirectAlbumTrack]:
    """
    Kompatible Kurzform für bestehende Aufrufer.

    Die eigentliche Zuordnung wird von build_album_matching_result()
    als globale Eins-zu-eins-Zuordnung berechnet.
    """
    return build_album_matching_result(
        songs,
        album,
    ).mapping


def build_album_matching_result(
    songs: list[Song],
    album: DirectAlbumResult,
) -> AlbumMatchingResult:
    """
    Erstellt eine globale Eins-zu-eins-Zuordnung zwischen lokalen Dateien
    und Albumtracks.

    Es wird nicht mehr eine Datei nach der anderen isoliert zugeordnet.
    Stattdessen entsteht eine vollständige Bewertungsmatrix. Anschließend
    sucht der ungarische Algorithmus die insgesamt beste Kombination.

    Berücksichtigt werden:
    - Titel im lokalen Tag
    - aus dem Dateinamen abgeleiteter Titel
    - Disc-/Trackpräfix im Dateinamen
    - lokale Disc-/Tracktags als schwächeres Signal
    - Dauer
    - Reihenfolge innerhalb der Auswahl

    Dadurch können falsche lokale Tags durch korrekte Dateinamen oder die
    Gesamtstruktur des Albums zuverlässig korrigiert werden.
    """
    if not songs or not album.tracks:
        return AlbumMatchingResult(
            matches=(),
            unmatched_local_indexes=tuple(
                range(len(songs))
            ),
            unused_track_indexes=tuple(
                range(len(album.tracks))
            ),
            ambiguous_local_indexes=(),
        )

    score_matrix: list[list[int]] = []
    reason_matrix: list[
        list[tuple[str, ...]]
    ] = []

    for local_index, song in enumerate(songs):
        score_row: list[int] = []
        reason_row: list[
            tuple[str, ...]
        ] = []

        for track_index, track in enumerate(
            album.tracks
        ):
            score, reasons = _score_pair(
                song,
                track,
                local_index=local_index,
                track_index=track_index,
            )
            score_row.append(score)
            reason_row.append(
                tuple(reasons)
            )

        score_matrix.append(score_row)
        reason_matrix.append(reason_row)

    assignments = _maximum_weight_assignment(
        score_matrix
    )

    matches: list[AlbumTrackMatch] = []
    unmatched_local: list[int] = []
    used_tracks: set[int] = set()
    ambiguous_local: list[int] = []

    for local_index, track_index in enumerate(
        assignments
    ):
        if (
            track_index is None
            or track_index >= len(album.tracks)
        ):
            unmatched_local.append(
                local_index
            )
            continue

        score = score_matrix[
            local_index
        ][track_index]
        reasons = reason_matrix[
            local_index
        ][track_index]

        # Sehr schwache Ergebnisse werden nicht automatisch übernommen.
        if score < 30:
            unmatched_local.append(
                local_index
            )
            continue

        row_scores = sorted(
            score_matrix[local_index],
            reverse=True,
        )
        gap = (
            row_scores[0] - row_scores[1]
            if len(row_scores) > 1
            else row_scores[0]
        )
        confidence = _confidence_label(
            score,
            gap,
        )

        if confidence == "Mehrdeutig":
            ambiguous_local.append(
                local_index
            )

        matches.append(
            AlbumTrackMatch(
                local_index=local_index,
                track_index=track_index,
                track=album.tracks[
                    track_index
                ],
                score=score,
                confidence=confidence,
                reasons=reasons,
            )
        )
        used_tracks.add(track_index)

    unused_tracks = [
        index
        for index in range(
            len(album.tracks)
        )
        if index not in used_tracks
    ]

    return AlbumMatchingResult(
        matches=tuple(matches),
        unmatched_local_indexes=tuple(
            unmatched_local
        ),
        unused_track_indexes=tuple(
            unused_tracks
        ),
        ambiguous_local_indexes=tuple(
            ambiguous_local
        ),
    )


def _score_pair(
    song: Song,
    track: DirectAlbumTrack,
    *,
    local_index: int,
    track_index: int,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    local_title = _normalize(
        song.title
    )
    source_title = _normalize(
        track.title
    )
    filename_title = _normalize(
        _title_from_filename(
            song.path
        )
    )

    if (
        local_title
        and local_title == source_title
    ):
        score += 95
        reasons.append(
            "Titel-Tag stimmt exakt"
        )
    elif (
        local_title
        and _simplify_title(
            song.title
        )
        == _simplify_title(
            track.title
        )
    ):
        score += 70
        reasons.append(
            "Titel-Tag stimmt vereinfacht"
        )

    if (
        filename_title
        and filename_title == source_title
    ):
        score += 120
        reasons.append(
            "Titel aus Dateiname stimmt exakt"
        )
    elif (
        filename_title
        and _simplify_title(
            _title_from_filename(
                song.path
            )
        )
        == _simplify_title(
            track.title
        )
    ):
        score += 90
        reasons.append(
            "Titel aus Dateiname stimmt vereinfacht"
        )

    filename_disc, filename_track = (
        _numbers_from_filename(
            song.path
        )
    )
    source_disc = _as_int(
        track.disc
    ) or 1
    source_track = _as_int(
        track.track
    )

    if (
        filename_track is not None
        and source_track is not None
    ):
        if (
            filename_track == source_track
            and (
                filename_disc is None
                or filename_disc
                == source_disc
            )
        ):
            score += 130
            reasons.append(
                "Tracknummer aus Dateiname stimmt"
            )
        else:
            score -= 55

    local_track = _as_int(
        song.track
    )
    local_disc = _as_int(
        song.disc
    ) or 1

    if (
        local_track is not None
        and source_track is not None
        and local_track == source_track
        and local_disc == source_disc
    ):
        score += 25
        reasons.append(
            "Lokaler Disc-/Tracktag stimmt"
        )

    local_duration_ms = _local_duration_ms(
        song.path
    )

    if (
        local_duration_ms is not None
        and track.duration_ms is not None
    ):
        difference = abs(
            local_duration_ms
            - track.duration_ms
        )

        if difference <= 1500:
            score += 35
            reasons.append(
                "Dauer nahezu identisch"
            )
        elif difference <= 4000:
            score += 22
            reasons.append(
                "Dauer ähnlich"
            )
        elif difference <= 10000:
            score += 8
        elif difference >= 30000:
            score -= 20

    # Reihenfolge ist nur ein leichtes Zusatzsignal.
    if local_index == track_index:
        score += 12
        reasons.append(
            "Position stimmt"
        )
    else:
        distance = abs(
            local_index - track_index
        )
        score -= min(
            12,
            distance,
        )

    return score, reasons



@lru_cache(maxsize=4096)
def _local_duration_ms(
    filepath: str,
) -> int | None:
    path = Path(filepath)

    if not path.is_file():
        return None

    try:
        audio = MutagenFile(path)
    except Exception:
        return None

    info = getattr(
        audio,
        "info",
        None,
    )
    length = getattr(
        info,
        "length",
        None,
    )

    if length is None:
        return None

    try:
        return round(
            float(length) * 1000
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def _maximum_weight_assignment(
    scores: list[list[int]],
) -> list[int | None]:
    """
    Ungarischer Algorithmus für maximale Gewichtung.

    Rechteckige Matrizen werden auf eine quadratische Matrix mit
    neutralen Dummy-Zuordnungen erweitert.
    """
    row_count = len(scores)
    column_count = max(
        (
            len(row)
            for row in scores
        ),
        default=0,
    )
    size = max(
        row_count,
        column_count,
    )

    if size == 0:
        return []

    maximum = max(
        (
            value
            for row in scores
            for value in row
        ),
        default=0,
    )

    costs = [
        [
            maximum - (
                scores[row][column]
                if (
                    row < row_count
                    and column
                    < len(scores[row])
                )
                else 0
            )
            for column in range(size)
        ]
        for row in range(size)
    ]

    # Klassische O(n³)-Implementierung, 1-basiert.
    u = [0] * (size + 1)
    v = [0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)

    for row in range(1, size + 1):
        p[0] = row
        column_0 = 0
        minimum_values = [
            float("inf")
        ] * (size + 1)
        used = [False] * (size + 1)

        while True:
            used[column_0] = True
            current_row = p[column_0]
            delta = float("inf")
            column_1 = 0

            for column in range(
                1,
                size + 1,
            ):
                if used[column]:
                    continue

                current = (
                    costs[
                        current_row - 1
                    ][column - 1]
                    - u[current_row]
                    - v[column]
                )

                if (
                    current
                    < minimum_values[column]
                ):
                    minimum_values[
                        column
                    ] = current
                    way[column] = column_0

                if (
                    minimum_values[column]
                    < delta
                ):
                    delta = (
                        minimum_values[column]
                    )
                    column_1 = column

            for column in range(
                size + 1
            ):
                if used[column]:
                    u[p[column]] += delta
                    v[column] -= delta
                else:
                    minimum_values[
                        column
                    ] -= delta

            column_0 = column_1

            if p[column_0] == 0:
                break

        while True:
            column_1 = way[column_0]
            p[column_0] = p[column_1]
            column_0 = column_1

            if column_0 == 0:
                break

    assignment: list[
        int | None
    ] = [None] * row_count

    for column in range(
        1,
        size + 1,
    ):
        row = p[column]

        if (
            1 <= row <= row_count
            and column <= column_count
        ):
            assignment[
                row - 1
            ] = column - 1

    return assignment


def _title_from_filename(
    filepath: str,
) -> str:
    stem = re.sub(
        r"\.[^.]+$",
        "",
        filepath.rsplit(
            "/",
            1,
        )[-1].rsplit(
            "\\",
            1,
        )[-1],
    )

    # Nummernpräfix entfernen: 09., 109., 1-09 usw.
    stem = re.sub(
        r"^\s*(?:\d{1,2}[-_.])?\d{1,3}\s*[.)_-]\s*",
        "",
        stem,
    )

    # Übliches Schema "Künstler - Titel".
    if " - " in stem:
        stem = stem.split(
            " - ",
            1,
        )[1]

    return stem.strip()


def _numbers_from_filename(
    filepath: str,
) -> tuple[int | None, int | None]:
    filename = filepath.rsplit(
        "/",
        1,
    )[-1].rsplit(
        "\\",
        1,
    )[-1]

    match = re.match(
        r"^\s*(\d{2,3})(?:\D|$)",
        filename,
    )

    if not match:
        return None, None

    raw = match.group(1)

    if len(raw) == 3:
        return (
            int(raw[0]),
            int(raw[1:]),
        )

    return None, int(raw)


def _confidence_label(
    score: int,
    gap: int,
) -> str:
    if score >= 180 and gap >= 35:
        return "Sehr sicher"

    if score >= 120 and gap >= 20:
        return "Sicher"

    if score >= 80 and gap >= 10:
        return "Wahrscheinlich"

    return "Mehrdeutig"


def _simplify_title(
    value: str,
) -> str:
    """
    Normalisiert leichte Schreibvarianten, ohne Remix- oder
    Instrumentalzusätze pauschal zu entfernen.
    """
    normalized = _normalize(value)
    normalized = re.sub(
        r"\bversion\b",
        "",
        normalized,
    )
    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized.strip()


def _lookup_apple_song(
    song_id: str,
    *,
    country: str,
) -> DirectAlbumResult:
    payload = _request_json(
        "https://itunes.apple.com/lookup",
        {
            "id": song_id,
            "country": country.upper(),
            "entity": "song",
        },
    )
    item = next(
        (
            result
            for result in payload.get(
                "results",
                [],
            )
            if (
                result.get("wrapperType")
                == "track"
                and result.get("kind")
                == "song"
            )
        ),
        None,
    )

    if item is None and country.upper() != "US":
        payload = _request_json(
            "https://itunes.apple.com/lookup",
            {
                "id": song_id,
                "country": "US",
                "entity": "song",
            },
        )
        item = next(
            (
                result
                for result in payload.get(
                    "results",
                    [],
                )
                if (
                    result.get("wrapperType")
                    == "track"
                    and result.get("kind")
                    == "song"
                )
            ),
            None,
        )

    if item is None:
        raise DirectAlbumLookupError(
            "Die Apple-Song-ID konnte über die "
            "offizielle Lookup-Schnittstelle nicht geladen werden."
        )

    track = DirectAlbumTrack(
        title=str(
            item.get(
                "trackName",
                "",
            )
        ),
        artist=str(
            item.get(
                "artistName",
                "",
            )
        ),
        album_artist=str(
            item.get(
                "collectionArtistName"
            )
            or item.get(
                "artistName",
                "",
            )
        ),
        album=str(
            item.get(
                "collectionName",
                "",
            )
        ),
        genre=str(
            item.get(
                "primaryGenreName",
                "",
            )
        ),
        year=_year_from_date(
            str(
                item.get(
                    "releaseDate",
                    "",
                )
            )
        ),
        track=str(
            item.get(
                "trackNumber",
                "",
            )
        ),
        total_tracks=str(
            item.get(
                "trackCount",
                "",
            )
        ),
        disc=str(
            item.get(
                "discNumber",
                "",
            )
        ),
        total_discs=str(
            item.get(
                "discCount",
                "",
            )
        ),
        duration_ms=_optional_int(
            item.get(
                "trackTimeMillis"
            )
        ),
        external_id=str(
            item.get(
                "trackId",
                "",
            )
        ),
    )

    return DirectAlbumResult(
        provider="apple_music",
        album=track.album,
        album_artist=(
            track.album_artist
        ),
        tracks=(track,),
    )


def lookup_apple_album_by_id(
    album_id: str,
    *,
    country: str = "DE",
) -> DirectAlbumResult:
    """Lädt eine vollständige Apple-Albumtrackliste über die offizielle Lookup-API."""
    return _lookup_apple_album(
        album_id,
        country=country,
    )


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
            external_id=str(
                item.get(
                    "trackId",
                    "",
                )
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


def lookup_musicbrainz_release_by_id(
    release_id: str,
) -> DirectAlbumResult:
    """Lädt die vollständige Trackliste eines MusicBrainz-Releases."""
    return _lookup_musicbrainz_release(
        release_id
    )


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
    global _mb_last_request_time

    is_musicbrainz = url.startswith(
        "https://musicbrainz.org/"
    )

    if is_musicbrainz:
        _mb_request_lock.acquire()

        wait = (
            _MB_REQUEST_INTERVAL
            - (
                time.monotonic()
                - _mb_last_request_time
            )
        )

        if wait > 0:
            time.sleep(wait)

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
    finally:
        if is_musicbrainz:
            _mb_last_request_time = (
                time.monotonic()
            )
            _mb_request_lock.release()


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
