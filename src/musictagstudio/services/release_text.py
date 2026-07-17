from __future__ import annotations

from collections import Counter
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess

from ..audio_analysis.ffmpeg_tools import (
    find_ffmpeg,
)
from ..cover_management.image_tools import (
    safe_filename,
)
from ..direct_album_lookup import (
    DirectAlbumLookupError,
    lookup_apple_album_by_id,
)
from ..models.song import Song
from ..providers.apple_music import (
    AppleMusicProviderError,
    search_album as search_apple_album,
)
from ..settings import AppSettings


@dataclass(frozen=True)
class ReleaseTextResult:
    path: Path
    text: str
    analyzed_files: int
    total_files: int


@dataclass(frozen=True)
class QuickAudioInfo:
    path: str
    codec: str = ""
    sample_rate: int = 0
    bit_depth: int = 0
    bitrate: int = 0


def create_release_text(
    songs: list[Song],
    settings: AppSettings,
) -> ReleaseTextResult:
    if not songs:
        raise ValueError(
            "Es wurden keine Audiodateien ausgewählt."
        )

    ordered = sorted(
        songs,
        key=_track_sort_key,
    )
    first = ordered[0]
    album_directory = Path(
        first.path
    ).parent
    album_artist = (
        first.album_artist
        or first.artist
        or "Unbekannter Interpret"
    )
    album = (
        first.album
        or album_directory.name
    )
    year = _most_common(
        song.year
        for song in ordered
    )
    year = _year_only(
        year
    )
    genre = _most_common(
        song.genre
        for song in ordered
    )
    formats = sorted(
        {
            Path(song.path)
            .suffix
            .lstrip(".")
            .upper()
            for song in ordered
            if Path(
                song.path
            ).suffix
        }
    )
    format_text = (
        ", ".join(
            formats
        )
        if formats
        else "Unbekannt"
    )

    installation = find_ffmpeg()
    infos: list[
        QuickAudioInfo
    ] = []

    if installation.available:
        max_workers = min(
            4,
            max(
                1,
                len(ordered),
            ),
        )

        with ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:
            futures = {
                executor.submit(
                    _probe_quick,
                    song.path,
                    installation.ffprobe_path,
                ): song.path
                for song in ordered
            }

            for future in as_completed(
                futures
            ):
                try:
                    info = future.result()
                except Exception:
                    continue

                if info is not None:
                    infos.append(
                        info
                    )

    quality = _quality_text(
        infos
    )
    apple_titles = _load_apple_track_titles(
        ordered,
        settings,
    )
    tracklist = _build_tracklist(
        ordered,
        apple_titles=apple_titles,
    )

    header = (
        f"{album_artist} - {album}"
        + (
            f" ({year})"
            if year
            else ""
        )
    )
    text = (
        "[center][img]xxxxxxxxxx[/img]\n"
        f"[b]{header}\n\n"
        "Infos[/b]:\n"
        f"[b]Genre[/b]: {genre or 'Unbekannt'}\n"
        f"[b]Format[/b]: {format_text}, RAR\n"
        f"[b]Qualität/Bitrate[/b]: {quality}\n"
        "[b]Hoster[/b]: DDownload, Rapidgator\n"
        "[b]Größe[/b]: \n\n"
        "[b]Tracklist[/b]:\n"
        f"[spoiler]{tracklist}[/spoiler]\n\n"
        "[b]Links[/b]:\n"
        "xxxxxxxxxx\n\n"
        f"{album_artist}, {genre},"
    )

    artist_folder = _resolve_artist_folder(
        album_directory,
        album_artist,
        settings.artist_folder_levels_up,
    )

    artist_folder.mkdir(
        parents=True,
        exist_ok=True,
    )
    base = safe_filename(
        f"{album_artist} - {album}"
    )
    path = (
        artist_folder
        / f"{base}.txt"
    )
    path.write_text(
        text,
        encoding="utf-8",
    )

    return ReleaseTextResult(
        path=path,
        text=text,
        analyzed_files=len(
            infos
        ),
        total_files=len(
            ordered
        ),
    )



def _load_apple_track_titles(
    songs: list[Song],
    settings: AppSettings,
) -> dict[tuple[int, int], str]:
    """Lädt die originalen Apple-Music-Titel für die BBCode-Tracklist.

    Die lokalen Tags bleiben unverändert. Kann Apple nicht sicher geladen werden,
    fällt die Ausgabe auf die lokalen Titel zurück.
    """
    if not songs:
        return {}

    first = songs[0]
    album = str(first.album or "").strip()
    artist = str(
        first.album_artist
        or first.artist
        or ""
    ).strip()

    if not album:
        return {}

    expected_track_count = max(
        [
            _as_int(song.total_tracks)
            for song in songs
        ]
        + [len(songs)]
    )
    year = _year_only(
        _most_common(
            song.year
            for song in songs
        )
    )
    countries = tuple(
        dict.fromkeys(
            (
                settings.apple_country.upper(),
                "US",
            )
        )
    )
    album_variants = _album_title_variants(
        album
    )

    for country in countries:
        candidates = []

        for variant in album_variants:
            try:
                candidates.extend(
                    search_apple_album(
                        variant,
                        artist,
                        expected_track_count=expected_track_count,
                        wanted_year=year,
                        country=country,
                        limit=30,
                    )
                )
            except AppleMusicProviderError:
                continue

        if not candidates:
            continue

        unique = {}

        for candidate in candidates:
            previous = unique.get(
                candidate.collection_id
            )

            if (
                previous is None
                or candidate.confidence
                > previous.confidence
            ):
                unique[
                    candidate.collection_id
                ] = candidate

        ranked = sorted(
            unique.values(),
            key=lambda candidate: (
                candidate.track_count
                == expected_track_count,
                candidate.confidence,
            ),
            reverse=True,
        )

        for candidate in ranked[:5]:
            try:
                result = lookup_apple_album_by_id(
                    candidate.collection_id,
                    country=country,
                )
            except DirectAlbumLookupError:
                continue

            mapping = {
                (
                    _as_int(track.disc) or 1,
                    _as_int(track.track),
                ): track.title.strip()
                for track in result.tracks
                if (
                    _as_int(track.track)
                    and track.title.strip()
                )
            }

            if len(mapping) >= min(
                len(songs),
                expected_track_count,
            ):
                return mapping

    return {}


def _album_title_variants(
    album: str,
) -> tuple[str, ...]:
    variants: list[str] = []

    for value in (
        album,
        album.replace("/", " "),
        album.replace("/", "-"),
    ):
        value = re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

        if (
            value
            and value.casefold()
            not in {
                item.casefold()
                for item in variants
            }
        ):
            variants.append(value)

    return tuple(variants)


def _build_tracklist(
    songs: list[Song],
    *,
    apple_titles: dict[tuple[int, int], str] | None = None,
) -> str:
    apple_titles = apple_titles or {}
    discs: dict[int, list[Song]] = {}

    for song in songs:
        disc = _as_int(song.disc) or 1
        discs.setdefault(
            disc,
            [],
        ).append(song)

    multi_disc = (
        len(discs) > 1
        or max(
            [
                _as_int(song.total_discs)
                for song in songs
            ]
            + [1]
        ) > 1
    )
    sections: list[str] = []

    for disc in sorted(discs):
        disc_songs = sorted(
            discs[disc],
            key=_track_sort_key,
        )
        lines = [
            _track_line(
                song,
                index,
                apple_title=apple_titles.get(
                    (
                        disc,
                        _as_int(song.track),
                    )
                ),
            )
            for index, song in enumerate(
                disc_songs,
                start=1,
            )
        ]

        if multi_disc:
            sections.append(
                f"[b]CD{disc}[/b]:\n"
                + "\n".join(lines)
            )
        else:
            sections.append(
                "\n".join(lines)
            )

    return "\n\n".join(sections)


def _resolve_artist_folder(
    album_directory: Path,
    album_artist: str,
    fallback_levels_up: int,
) -> Path:
    wanted = _folder_key(
        album_artist
    )

    for parent in (
        album_directory.parent,
        *album_directory.parents,
    ):
        if (
            wanted
            and _folder_key(
                parent.name
            )
            == wanted
        ):
            return parent

    current = album_directory

    for _ in range(
        max(
            1,
            fallback_levels_up,
        )
    ):
        current = current.parent

    return current


def _folder_key(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(
            value or ""
        ).casefold(),
    )


def _probe_quick(
    filepath: str,
    ffprobe_path: str,
) -> QuickAudioInfo | None:
    completed = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            (
                "stream=codec_name,sample_rate,"
                "bits_per_raw_sample,bits_per_sample,bit_rate:"
                "format=bit_rate"
            ),
            "-of",
            "json",
            filepath,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
        creationflags=int(
            getattr(
                subprocess,
                "CREATE_NO_WINDOW",
                0,
            )
        ),
    )

    if completed.returncode:
        return None

    payload = json.loads(
        completed.stdout
    )
    stream = next(
        iter(
            payload.get(
                "streams",
                [],
            )
        ),
        {},
    )
    format_info = payload.get(
        "format",
        {},
    )

    return QuickAudioInfo(
        path=filepath,
        codec=str(
            stream.get(
                "codec_name",
                "",
            )
        ),
        sample_rate=_as_int(
            stream.get(
                "sample_rate"
            )
        ),
        bit_depth=_as_int(
            stream.get(
                "bits_per_raw_sample"
            )
            or stream.get(
                "bits_per_sample"
            )
        ),
        bitrate=_as_int(
            stream.get(
                "bit_rate"
            )
            or format_info.get(
                "bit_rate"
            )
        ),
    )


def _quality_text(
    infos: list[
        QuickAudioInfo
    ],
) -> str:
    if not infos:
        return (
            "nicht ermittelt "
            "(ffprobe nicht verfügbar)"
        )

    bit_depth = _most_common_int(
        info.bit_depth
        for info in infos
    )
    sample_rate = _most_common_int(
        info.sample_rate
        for info in infos
    )
    bitrates = [
        info.bitrate
        for info in infos
        if info.bitrate > 0
    ]
    bitrate = (
        round(
            sum(bitrates)
            / len(bitrates)
            / 1000
        )
        if bitrates
        else 0
    )

    parts = [
        (
            f"{bit_depth}-Bit"
            if bit_depth
            else "Bit-Tiefe unbekannt"
        ),
        (
            _sample_rate_text(
                sample_rate
            )
            if sample_rate
            else "Abtastrate unbekannt"
        ),
        (
            f"~{bitrate} kbps"
            if bitrate
            else "Bitrate unbekannt"
        ),
    ]

    return ", ".join(
        parts
    )


def _sample_rate_text(
    sample_rate: int,
) -> str:
    khz = (
        sample_rate
        / 1000
    )

    if khz.is_integer():
        value = str(
            int(khz)
        )
    else:
        value = (
            f"{khz:.1f}"
            .replace(
                ".",
                ",",
            )
        )

    return f"{value} kHz"


def _track_line(
    song: Song,
    fallback_index: int,
    *,
    apple_title: str | None = None,
) -> str:
    number = _as_int(
        song.track
    ) or fallback_index
    title = (
        str(apple_title or "").strip()
        or song.title
        or Path(
            song.path
        ).stem
    )

    return (
        f"{number:02d}. "
        f"{title}"
    )


def _track_sort_key(
    song: Song,
) -> tuple[
    int,
    int,
    str,
]:
    return (
        _as_int(
            song.disc
        )
        or 1,
        _as_int(
            song.track
        )
        or 9999,
        Path(
            song.path
        ).name.casefold(),
    )


def _most_common(
    values,
) -> str:
    cleaned = [
        str(value).strip()
        for value in values
        if str(
            value or ""
        ).strip()
    ]

    if not cleaned:
        return ""

    return Counter(
        cleaned
    ).most_common(
        1
    )[0][0]


def _most_common_int(
    values,
) -> int:
    cleaned = [
        int(value)
        for value in values
        if int(
            value or 0
        ) > 0
    ]

    if not cleaned:
        return 0

    return Counter(
        cleaned
    ).most_common(
        1
    )[0][0]


def _year_only(
    value: str,
) -> str:
    match = re.search(
        r"\b(?:19|20)\d{2}\b",
        str(
            value or ""
        ),
    )

    return (
        match.group(0)
        if match
        else str(
            value or ""
        ).strip()
    )


def _as_int(
    value,
) -> int:
    try:
        return int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0
