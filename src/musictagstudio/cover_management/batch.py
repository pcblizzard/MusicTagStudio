from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .manager import CoverManager
from .models import CoverCandidate
from ..models.song import Song


@dataclass(frozen=True)
class AlbumCoverPlan:
    album_artist: str
    album: str
    songs: tuple[Song, ...]
    existing_master: CoverCandidate | None

    @property
    def display_name(self) -> str:
        return (
            f"{self.album_artist} – {self.album}"
        )

    @property
    def track_count(self) -> int:
        return len(self.songs)


def build_album_cover_plans(
    manager: CoverManager,
    songs: list[Song],
) -> list[AlbumCoverPlan]:
    grouped = manager.group_songs_by_album(
        songs
    )
    plans: list[AlbumCoverPlan] = []

    for album_songs in grouped.values():
        first_song = album_songs[0]
        plans.append(
            AlbumCoverPlan(
                album_artist=(
                    first_song.album_artist
                    or first_song.artist
                    or "Unbekannter Künstler"
                ),
                album=(
                    first_song.album
                    or Path(
                        first_song.path
                    ).parent.name
                ),
                songs=tuple(album_songs),
                existing_master=(
                    manager.find_existing_master(
                        first_song
                    )
                ),
            )
        )

    return sorted(
        plans,
        key=lambda plan:
        plan.display_name.casefold(),
    )
