from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from .diagnostics import project_root
from .models.song import Song


@dataclass(frozen=True)
class MusicSource:
    source_id: str
    name: str
    path: str
    enabled: bool = True

    @property
    def available(self) -> bool:
        return Path(self.path).is_dir()


@dataclass(frozen=True)
class IndexedAlbum:
    key: str
    album: str
    album_artist: str
    folder: str
    representative_file: str
    source_id: str
    source_name: str
    source_path: str
    source_online: bool
    track_count: int
    last_seen: str


@dataclass(frozen=True)
class SourceScanSummary:
    source: MusicSource
    albums: tuple[IndexedAlbum, ...]
    song_count: int
    failure_count: int


def new_source(
    path: str,
    *,
    name: str = "",
    enabled: bool = True,
) -> MusicSource:
    clean_path = str(Path(path))
    clean_name = name.strip() or Path(clean_path).name or clean_path

    return MusicSource(
        source_id=uuid.uuid4().hex,
        name=clean_name,
        path=clean_path,
        enabled=enabled,
    )


def index_path() -> Path:
    path = (
        project_root()
        / ".musictagstudio"
        / "library_index.json"
    )
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def load_library_index() -> list[IndexedAlbum]:
    path = index_path()

    if not path.is_file():
        return []

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []

    albums: list[IndexedAlbum] = []

    for item in payload.get(
        "albums",
        [],
    ):
        try:
            albums.append(
                IndexedAlbum(
                    key=str(item["key"]),
                    album=str(item.get("album", "")),
                    album_artist=str(
                        item.get(
                            "album_artist",
                            "",
                        )
                    ),
                    folder=str(item.get("folder", "")),
                    representative_file=str(
                        item.get(
                            "representative_file",
                            "",
                        )
                    ),
                    source_id=str(
                        item.get(
                            "source_id",
                            "",
                        )
                    ),
                    source_name=str(
                        item.get(
                            "source_name",
                            "",
                        )
                    ),
                    source_path=str(
                        item.get(
                            "source_path",
                            "",
                        )
                    ),
                    source_online=bool(
                        item.get(
                            "source_online",
                            False,
                        )
                    ),
                    track_count=int(
                        item.get(
                            "track_count",
                            0,
                        )
                    ),
                    last_seen=str(
                        item.get(
                            "last_seen",
                            "",
                        )
                    ),
                )
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

    return albums


def save_library_index(
    albums: list[IndexedAlbum],
) -> None:
    payload = {
        "version": 1,
        "updated_at": _now(),
        "albums": [
            asdict(album)
            for album in albums
        ],
    }
    index_path().write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def update_source_availability(
    albums: list[IndexedAlbum],
    sources: tuple[MusicSource, ...],
) -> list[IndexedAlbum]:
    source_status = {
        source.source_id: source.available
        for source in sources
    }

    return [
        IndexedAlbum(
            **{
                **asdict(album),
                "source_online": source_status.get(
                    album.source_id,
                    False,
                ),
            }
        )
        for album in albums
    ]


def scan_source(
    source: MusicSource,
) -> SourceScanSummary:
    # Lokaler Import verhindert den Start-Zirkel:
    # settings -> library_sources -> services -> proposal -> settings.
    from .services.scanner import scan_folder_detailed

    result = scan_folder_detailed(
        source.path
    )
    grouped: dict[
        tuple[str, str, str],
        list[Song],
    ] = {}

    for song in result.songs:
        folder = str(
            Path(song.path).parent
        )
        artist = (
            song.album_artist
            or song.artist
        ).strip()
        album = song.album.strip()
        group_key = (
            _key(artist),
            _key(album),
            folder.casefold(),
        )
        grouped.setdefault(
            group_key,
            [],
        ).append(song)

    now = _now()
    albums: list[IndexedAlbum] = []

    for songs in grouped.values():
        first = songs[0]
        artist = (
            first.album_artist
            or first.artist
        ).strip()
        album = first.album.strip()
        folder = str(
            Path(first.path).parent
        )
        albums.append(
            IndexedAlbum(
                key=_album_key(
                    artist,
                    album,
                    folder,
                ),
                album=album,
                album_artist=artist,
                folder=folder,
                representative_file=first.path,
                source_id=source.source_id,
                source_name=source.name,
                source_path=source.path,
                source_online=True,
                track_count=len(songs),
                last_seen=now,
            )
        )

    return SourceScanSummary(
        source=source,
        albums=tuple(albums),
        song_count=len(result.songs),
        failure_count=len(result.failures),
    )


def merge_scan_results(
    existing: list[IndexedAlbum],
    summaries: list[SourceScanSummary],
    sources: tuple[MusicSource, ...],
) -> list[IndexedAlbum]:
    scanned_ids = {
        summary.source.source_id
        for summary in summaries
    }
    retained = [
        album
        for album in existing
        if album.source_id not in scanned_ids
    ]

    for summary in summaries:
        retained.extend(
            summary.albums
        )

    retained = update_source_availability(
        retained,
        sources,
    )

    return sorted(
        retained,
        key=lambda album: (
            album.album_artist.casefold(),
            album.album.casefold(),
            album.folder.casefold(),
        ),
    )


def albums_for_artist(
    albums: list[IndexedAlbum],
    artist: str,
) -> list[IndexedAlbum]:
    wanted = _key(artist)

    return [
        album
        for album in albums
        if _key(album.album_artist)
        == wanted
    ]


def _album_key(
    artist: str,
    album: str,
    folder: str,
) -> str:
    return "|".join(
        (
            _key(artist),
            _key(album),
            str(folder).casefold(),
        )
    )


def _key(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(
            value or ""
        ).casefold(),
    )


def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(
        timespec="seconds"
    )
