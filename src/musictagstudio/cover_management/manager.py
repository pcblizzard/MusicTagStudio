from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from .image_tools import (
    extension_for_mime,
    inspect_image,
    resize_to_jpeg,
    safe_filename,
)
from .models import CoverCandidate
from .providers import (
    download,
    search_apple_cover,
    search_caa_cover,
)
from ..direct_references import (
    DirectAlbumReference,
)
from ..models.song import Song
from ..services.cover import embed_cover
from ..settings import AppSettings


@dataclass(frozen=True)
class CoverWorkflowResult:
    master_path: Path
    folder_cover_path: Path
    embedded_files: int


class CoverManager:
    _search_cache: dict[
        tuple[str, ...],
        tuple[CoverCandidate, ...],
    ] = {}
    _cache_lock = Lock()

    def __init__(
        self,
        settings: AppSettings,
    ):
        self.settings = settings

    def search_candidates(
        self,
        song: Song,
        direct_reference: DirectAlbumReference | None = None,
    ) -> list[CoverCandidate]:
        album_artist = (
            song.album_artist
            or song.artist
        )
        cache_key = (
            song.album.casefold(),
            album_artist.casefold(),
            self.settings.apple_country,
            self.settings.selected_cover_source,
            str(
                self.settings.cover_fallback_enabled
            ),
            direct_reference.provider
            if direct_reference
            else "",
            direct_reference.reference_id
            if direct_reference
            else "",
            direct_reference.reference_type
            if direct_reference
            else "",
        )

        with self._cache_lock:
            cached = self._search_cache.get(
                cache_key
            )

        if cached is not None:
            return list(cached)

        candidates = self._local_master_candidates(
            song
        )

        order = [
            self.settings.selected_cover_source
        ]

        if self.settings.cover_fallback_enabled:
            order += [
                source
                for source in (
                    "apple_music",
                    "cover_art_archive",
                )
                if source not in order
            ]

        with ThreadPoolExecutor(
            max_workers=len(order),
        ) as executor:
            futures = {}

            for source in order:
                if source == "apple_music":
                    apple_id = (
                        direct_reference.reference_id
                        if direct_reference
                        and direct_reference.provider
                        == "apple_music"
                        else ""
                    )
                    future = executor.submit(
                        search_apple_cover,
                        song.album,
                        album_artist,
                        self.settings.apple_country,
                        apple_id,
                    )
                    futures[future] = source

                elif source == "cover_art_archive":
                    release_id = ""
                    release_group_id = ""

                    if (
                        direct_reference
                        and direct_reference.provider
                        == "musicbrainz"
                    ):
                        if (
                            direct_reference.reference_type
                            == "release"
                        ):
                            release_id = (
                                direct_reference.reference_id
                            )
                        else:
                            release_group_id = (
                                direct_reference.reference_id
                            )

                    future = executor.submit(
                        search_caa_cover,
                        song.album,
                        album_artist,
                        release_id,
                        release_group_id,
                    )
                    futures[future] = source

            for future in as_completed(futures):
                try:
                    candidates.extend(
                        future.result()
                    )
                except Exception:
                    continue

        candidates = self._deduplicate(
            candidates
        )
        candidates.sort(
            key=lambda candidate: (
                not candidate.is_local,
                -candidate.score,
                -candidate.width
                * candidate.height,
            )
        )

        with self._cache_lock:
            self._search_cache[
                cache_key
            ] = tuple(candidates)

        return candidates

    def load_preview(
        self,
        candidate: CoverCandidate,
    ) -> bytes:
        if candidate.data is not None:
            return candidate.data

        return download(
            candidate.preview_url
            or candidate.url
        )

    def hydrate(
        self,
        candidate: CoverCandidate,
    ) -> CoverCandidate:
        if candidate.data is not None:
            return candidate

        data = download(candidate.url)
        width, height, mime = inspect_image(data)
        score = (
            candidate.score
            + min(width, height) // 100
            + (10 if width == height else 0)
        )

        return candidate.with_data(
            data,
            width=width,
            height=height,
            mime=mime,
            score=score,
        )

    def apply(
        self,
        candidate: CoverCandidate,
        songs: list[Song],
    ) -> CoverWorkflowResult:
        hydrated = self.hydrate(candidate)

        if not songs or hydrated.data is None:
            raise ValueError(
                "Kein Cover oder keine Audiodateien ausgewählt."
            )

        album_dir = Path(
            songs[0].path
        ).parent
        album_artist = (
            songs[0].album_artist
            or songs[0].artist
            or "Unbekannter Künstler"
        )
        album = (
            songs[0].album
            or album_dir.name
        )
        base = safe_filename(
            f"{album_artist} - {album}"
        )
        extension = extension_for_mime(
            hydrated.mime
        )
        master_path = (
            album_dir
            / f"{base}.front.{extension}"
        )
        master_path.write_bytes(
            hydrated.data
        )

        embedded = resize_to_jpeg(
            hydrated.data,
            self.settings.embedded_cover_size,
            self.settings.embedded_cover_quality,
        )
        count = 0

        for song in songs:
            embed_cover(
                song.path,
                embedded,
            )
            count += 1

        artist_folder = album_dir

        for _ in range(
            max(
                1,
                self.settings.artist_folder_levels_up,
            )
        ):
            artist_folder = artist_folder.parent

        artist_folder.mkdir(
            parents=True,
            exist_ok=True,
        )
        folder_path = (
            artist_folder
            / f"{base}_400px.jpg"
        )
        folder_path.write_bytes(
            resize_to_jpeg(
                hydrated.data,
                self.settings.folder_cover_size,
                self.settings.folder_cover_quality,
            )
        )

        return CoverWorkflowResult(
            master_path,
            folder_path,
            count,
        )

    def _local_master_candidates(
        self,
        song: Song,
    ) -> list[CoverCandidate]:
        album_dir = Path(song.path).parent
        album_artist = (
            song.album_artist
            or song.artist
            or "Unbekannter Künstler"
        )
        album = (
            song.album
            or album_dir.name
        )
        base = safe_filename(
            f"{album_artist} - {album}"
        )

        for extension in (
            "jpg",
            "jpeg",
            "png",
            "webp",
        ):
            path = (
                album_dir
                / f"{base}.front.{extension}"
            )

            if not path.is_file():
                continue

            data = path.read_bytes()
            width, height, mime = inspect_image(
                data
            )

            return [
                CoverCandidate(
                    source="local",
                    source_label="Vorhandenes Master-Cover",
                    url=path.as_uri(),
                    preview_url=path.as_uri(),
                    width=width,
                    height=height,
                    mime=mime,
                    release_id="",
                    score=10_000,
                    data=data,
                    album=album,
                    artist=album_artist,
                    is_local=True,
                )
            ]

        return []

    @staticmethod
    def _deduplicate(
        candidates: list[CoverCandidate],
    ) -> list[CoverCandidate]:
        result: list[CoverCandidate] = []
        seen: set[
            tuple[str, str]
        ] = set()

        for candidate in candidates:
            key = (
                candidate.source,
                candidate.release_id
                or candidate.url,
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(candidate)

        return result
