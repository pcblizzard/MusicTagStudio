from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from mutagen import File as MutagenFile

from .models import (
    LibraryAuditSummary,
    LibraryIssue,
)
from ..models.song import Song
from ..services.cover import load_cover_info


REPLAYGAIN_TRACK_GAIN = "replaygain_track_gain"
REPLAYGAIN_ALBUM_GAIN = "replaygain_album_gain"


def audit_library(
    songs: list[Song],
) -> LibraryAuditSummary:
    issues: list[LibraryIssue] = []
    grouped = _group_by_album(songs)

    issues.extend(
        _check_duplicate_isrcs(songs)
    )

    for album_songs in grouped.values():
        issues.extend(
            _check_album_values(
                album_songs
            )
        )
        issues.extend(
            _check_track_numbers(
                album_songs
            )
        )
        issues.extend(
            _check_disc_numbers(
                album_songs
            )
        )
        issues.extend(
            _check_cover_consistency(
                album_songs
            )
        )
        issues.extend(
            _check_replaygain(
                album_songs
            )
        )

    issues.sort(
        key=lambda issue: (
            _severity_rank(
                issue.severity
            ),
            issue.category.casefold(),
            issue.album_display.casefold(),
            issue.title.casefold(),
        )
    )

    return LibraryAuditSummary(
        checked_files=len(songs),
        checked_albums=len(grouped),
        issues=tuple(issues),
    )


def _check_duplicate_isrcs(
    songs: list[Song],
) -> list[LibraryIssue]:
    by_isrc: dict[
        str,
        list[Song],
    ] = defaultdict(list)

    for song in songs:
        isrc = song.isrc.strip().upper()

        if isrc:
            by_isrc[isrc].append(song)

    issues: list[LibraryIssue] = []

    for isrc, matches in by_isrc.items():
        if len(matches) < 2:
            continue

        paths = "\n".join(
            song.path
            for song in matches
        )
        first = matches[0]

        issues.append(
            LibraryIssue(
                category="Doppelte ISRC",
                severity="warning",
                message=(
                    f"ISRC {isrc} kommt in "
                    f"{len(matches)} Dateien vor."
                ),
                album_artist=(
                    first.album_artist
                    or first.artist
                ),
                album=first.album,
                title=first.title,
                path=first.path,
                details=paths,
            )
        )

    return issues


def _check_album_values(
    songs: list[Song],
) -> list[LibraryIssue]:
    fields = {
        "Albumkünstler": [
            song.album_artist
            for song in songs
        ],
        "Album": [
            song.album
            for song in songs
        ],
        "Genre": [
            song.genre
            for song in songs
        ],
        "Jahr": [
            song.year
            for song in songs
        ],
        "Label": [
            song.label
            for song in songs
        ],
    }
    first = songs[0]
    issues: list[LibraryIssue] = []

    for label, values in fields.items():
        normalized = {
            value.strip()
            for value in values
            if value.strip()
        }

        if len(normalized) <= 1:
            continue

        issues.append(
            LibraryIssue(
                category="Uneinheitliche Albumwerte",
                severity="warning",
                message=(
                    f"{label} ist innerhalb "
                    "des Albums uneinheitlich."
                ),
                album_artist=(
                    first.album_artist
                    or first.artist
                ),
                album=first.album,
                title="",
                path=first.path,
                details="\n".join(
                    sorted(normalized)
                ),
            )
        )

    return issues


def _check_track_numbers(
    songs: list[Song],
) -> list[LibraryIssue]:
    """
    Prüft Tracknummern discweise.

    Dadurch sind beispielsweise Disc 1 / Track 2 und Disc 2 / Track 2
    erlaubt. Doppelte oder fehlende Nummern werden nur innerhalb
    derselben Disc gemeldet.
    """
    first = songs[0]
    issues: list[LibraryIssue] = []

    by_disc: dict[
        int,
        list[tuple[Song, int]],
    ] = defaultdict(list)

    invalid_songs: list[Song] = []

    for song in songs:
        track_number = _as_positive_int(
            song.track
        )
        disc_number = (
            _as_positive_int(
                song.disc
            )
            or 1
        )

        if track_number is None:
            invalid_songs.append(song)
            continue

        by_disc[disc_number].append(
            (
                song,
                track_number,
            )
        )

    for song in invalid_songs:
        issues.append(
            LibraryIssue(
                category="Tracknummer",
                severity="error",
                message=(
                    "Tracknummer fehlt oder "
                    "ist ungültig."
                ),
                album_artist=(
                    song.album_artist
                    or song.artist
                ),
                album=song.album,
                title=song.title,
                path=song.path,
            )
        )

    for disc_number, entries in sorted(
        by_disc.items()
    ):
        by_track: dict[
            int,
            list[Song],
        ] = defaultdict(list)

        for song, track_number in entries:
            by_track[
                track_number
            ].append(song)

        duplicate_numbers = [
            number
            for number, matches
            in by_track.items()
            if len(matches) > 1
        ]

        for number in sorted(
            duplicate_numbers
        ):
            matches = by_track[number]
            details = "\n".join(
                song.path
                for song in matches
            )

            issues.append(
                LibraryIssue(
                    category="Tracknummer",
                    severity="error",
                    message=(
                        f"Disc {disc_number}: "
                        f"Tracknummer {number} "
                        f"kommt {len(matches)}-mal vor."
                    ),
                    album_artist=(
                        first.album_artist
                        or first.artist
                    ),
                    album=first.album,
                    path=matches[0].path,
                    details=details,
                )
            )

        numbers = sorted(
            by_track
        )

        if numbers:
            expected = set(
                range(
                    1,
                    max(numbers) + 1,
                )
            )
            missing = sorted(
                expected - set(numbers)
            )

            if missing:
                issues.append(
                    LibraryIssue(
                        category="Tracknummer",
                        severity="warning",
                        message=(
                            f"Disc {disc_number}: "
                            "Lücken in der "
                            "Tracknummerierung: "
                            + ", ".join(
                                str(value)
                                for value in missing
                            )
                        ),
                        album_artist=(
                            first.album_artist
                            or first.artist
                        ),
                        album=first.album,
                        path=first.path,
                        details=(
                            "Vorhandene Tracknummern:\n"
                            + ", ".join(
                                str(value)
                                for value in numbers
                            )
                        ),
                    )
                )

        totals = {
            value
            for value in (
                _as_positive_int(
                    song.total_tracks
                )
                for song, _
                in entries
            )
            if value is not None
        }

        if len(totals) > 1:
            issues.append(
                LibraryIssue(
                    category="Track-Gesamtzahl",
                    severity="warning",
                    message=(
                        f"Disc {disc_number}: "
                        "Die Gesamtzahl der Tracks "
                        "ist uneinheitlich."
                    ),
                    album_artist=(
                        first.album_artist
                        or first.artist
                    ),
                    album=first.album,
                    path=first.path,
                    details=", ".join(
                        str(value)
                        for value in sorted(
                            totals
                        )
                    ),
                )
            )

    return issues

def _check_disc_numbers(
    songs: list[Song],
) -> list[LibraryIssue]:
    first = songs[0]
    issues: list[LibraryIssue] = []
    discs = [
        _as_positive_int(
            song.disc
        )
        for song in songs
    ]

    if any(
        disc is None
        for disc in discs
    ):
        issues.append(
            LibraryIssue(
                category="Discnummer",
                severity="warning",
                message=(
                    "Mindestens eine Discnummer "
                    "fehlt oder ist ungültig."
                ),
                album_artist=(
                    first.album_artist
                    or first.artist
                ),
                album=first.album,
                path=first.path,
            )
        )

    totals = {
        value
        for value in (
            _as_positive_int(
                song.total_discs
            )
            for song in songs
        )
        if value is not None
    }

    if len(totals) > 1:
        issues.append(
            LibraryIssue(
                category="Disc-Gesamtzahl",
                severity="warning",
                message=(
                    "Die Gesamtzahl der Discs "
                    "ist innerhalb des Albums uneinheitlich."
                ),
                album_artist=(
                    first.album_artist
                    or first.artist
                ),
                album=first.album,
                path=first.path,
                details=", ".join(
                    str(value)
                    for value in sorted(totals)
                ),
            )
        )

    return issues


def _check_cover_consistency(
    songs: list[Song],
) -> list[LibraryIssue]:
    first = songs[0]
    signatures: dict[
        tuple[int, str],
        list[Song],
    ] = defaultdict(list)
    missing: list[Song] = []

    for song in songs:
        signature = _embedded_cover_signature(
            song.path
        )

        if signature is None:
            missing.append(song)
        else:
            signatures[signature].append(
                song
            )

    issues: list[LibraryIssue] = []

    if missing:
        issues.append(
            LibraryIssue(
                category="Cover",
                severity="warning",
                message=(
                    f"{len(missing)} Datei(en) "
                    "besitzen kein eingebettetes Cover."
                ),
                album_artist=(
                    first.album_artist
                    or first.artist
                ),
                album=first.album,
                path=first.path,
                details="\n".join(
                    song.path
                    for song in missing
                ),
            )
        )

    if len(signatures) > 1:
        issues.append(
            LibraryIssue(
                category="Cover",
                severity="warning",
                message=(
                    "Im Album wurden unterschiedliche "
                    "eingebettete Cover erkannt."
                ),
                album_artist=(
                    first.album_artist
                    or first.artist
                ),
                album=first.album,
                path=first.path,
                details="\n".join(
                    (
                        f"{count} Datei(en): "
                        f"{signature[0]} Byte · "
                        f"{signature[1][:12]}"
                    )
                    for signature, matches
                    in signatures.items()
                    for count in [len(matches)]
                ),
            )
        )

    return issues


def _check_replaygain(
    songs: list[Song],
) -> list[LibraryIssue]:
    first = songs[0]
    missing_track = []
    missing_album = []

    for song in songs:
        tags = _audio_tags(song.path)

        if tags is None:
            continue

        if not _has_tag(
            tags,
            REPLAYGAIN_TRACK_GAIN,
        ):
            missing_track.append(song)

        if not _has_tag(
            tags,
            REPLAYGAIN_ALBUM_GAIN,
        ):
            missing_album.append(song)

    issues: list[LibraryIssue] = []

    if missing_track:
        issues.append(
            LibraryIssue(
                category="ReplayGain",
                severity="info",
                message=(
                    f"{len(missing_track)} Datei(en) "
                    "besitzen keinen Track-Gain."
                ),
                album_artist=(
                    first.album_artist
                    or first.artist
                ),
                album=first.album,
                path=first.path,
                details="\n".join(
                    song.path
                    for song in missing_track
                ),
            )
        )

    if missing_album:
        issues.append(
            LibraryIssue(
                category="ReplayGain",
                severity="info",
                message=(
                    f"{len(missing_album)} Datei(en) "
                    "besitzen keinen Album-Gain."
                ),
                album_artist=(
                    first.album_artist
                    or first.artist
                ),
                album=first.album,
                path=first.path,
                details="\n".join(
                    song.path
                    for song in missing_album
                ),
            )
        )

    return issues


def _embedded_cover_signature(
    filepath: str,
) -> tuple[int, str] | None:
    try:
        info = load_cover_info(
            filepath
        )
    except Exception:
        return None

    if info is None:
        return None

    return (
        len(info.data),
        info.md5,
    )

def _audio_tags(
    filepath: str,
):
    path = Path(filepath)

    if not path.is_file():
        return None

    try:
        audio = MutagenFile(filepath)
    except Exception:
        return None

    if audio is None:
        return None

    return getattr(
        audio,
        "tags",
        None,
    )


def _has_tag(
    tags,
    tag_name: str,
) -> bool:
    normalized = tag_name.casefold()

    try:
        keys = list(tags.keys())
    except AttributeError:
        return False

    for key in keys:
        key_text = str(key).casefold()

        if normalized in key_text:
            return True

    return False


def _cover_bytes(
    value,
) -> bytes | None:
    if isinstance(value, bytes):
        return value

    if isinstance(value, list):
        for item in value:
            raw = _cover_bytes(item)

            if raw:
                return raw

    data = getattr(
        value,
        "data",
        None,
    )

    if isinstance(data, bytes):
        return data

    try:
        return bytes(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _md5(
    data: bytes,
) -> str:
    import hashlib

    return hashlib.md5(
        data,
        usedforsecurity=False,
    ).hexdigest()


def _group_by_album(
    songs: list[Song],
) -> dict[
    tuple[str, str, str],
    list[Song],
]:
    grouped: dict[
        tuple[str, str, str],
        list[Song],
    ] = {}

    for song in songs:
        directory = str(
            Path(song.path).parent.resolve()
        )
        key = (
            song.album.casefold(),
            directory.casefold(),
            "",
        )
        grouped.setdefault(
            key,
            [],
        ).append(song)

    return grouped


def _as_positive_int(
    value: str,
) -> int | None:
    try:
        number = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    return number if number > 0 else None


def _severity_rank(
    severity: str,
) -> int:
    return {
        "error": 0,
        "warning": 1,
        "info": 2,
    }.get(
        severity,
        3,
    )
