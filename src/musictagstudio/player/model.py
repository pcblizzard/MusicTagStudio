from __future__ import annotations

from dataclasses import dataclass, field
import random

from ..models.song import Song


@dataclass
class PlaybackQueue:
    songs: list[Song] = field(default_factory=list)
    current_index: int = -1
    repeat_mode: str = "off"
    shuffle_mode: str = "off"
    _shuffle_remaining: list[int] = field(default_factory=list)
    _history: list[int] = field(default_factory=list)
    _forward_history: list[int] = field(default_factory=list)

    @property
    def current(self) -> Song | None:
        if 0 <= self.current_index < len(self.songs):
            return self.songs[self.current_index]
        return None

    @property
    def shuffle(self) -> bool:
        return self.shuffle_mode != "off"

    def replace(self, songs: list[Song], start_index: int = 0) -> Song | None:
        self.songs = list(songs)
        self.current_index = (
            max(0, min(start_index, len(self.songs) - 1))
            if self.songs
            else -1
        )
        self._history = []
        self._forward_history = []
        self._reset_shuffle_remaining()
        return self.current

    def set_shuffle(self, enabled: bool) -> None:
        self.shuffle_mode = "history" if enabled else "off"
        self._history = []
        self._forward_history = []
        self._reset_shuffle_remaining()

    def cycle_shuffle(self) -> str:
        modes = ("off", "history", "fresh")
        self.shuffle_mode = modes[
            (modes.index(self.shuffle_mode) + 1) % len(modes)
        ]
        self._history = []
        self._forward_history = []
        self._reset_shuffle_remaining()
        return self.shuffle_mode

    def cycle_repeat(self) -> str:
        modes = ("off", "all", "one")
        self.repeat_mode = modes[(modes.index(self.repeat_mode) + 1) % len(modes)]
        return self.repeat_mode

    def play(self, index: int) -> Song | None:
        if not (0 <= index < len(self.songs)):
            return None
        if self.current_index >= 0 and self.current_index != index:
            self._history.append(self.current_index)
        self._forward_history = []
        self.current_index = index
        self._reset_shuffle_remaining()
        return self.current

    def remove(self, index: int) -> Song | None:
        if not (0 <= index < len(self.songs)):
            return self.current
        current_song = self.current
        removed_current = index == self.current_index
        self.songs.pop(index)
        if not self.songs:
            self.current_index = -1
        elif removed_current:
            self.current_index = min(index, len(self.songs) - 1)
        elif current_song is not None:
            self.current_index = next(
                (
                    position
                    for position, song in enumerate(self.songs)
                    if song is current_song
                ),
                min(self.current_index, len(self.songs) - 1),
            )
        self._history = []
        self._forward_history = []
        self._reset_shuffle_remaining()
        return self.current

    def move_next(self, index: int) -> Song | None:
        if not (0 <= index < len(self.songs)) or index == self.current_index:
            return self.current
        current_song = self.current
        song = self.songs.pop(index)
        current_position = next(
            (
                position
                for position, candidate in enumerate(self.songs)
                if candidate is current_song
            ),
            -1,
        )
        self.songs.insert(min(current_position + 1, len(self.songs)), song)
        self.current_index = next(
            position
            for position, candidate in enumerate(self.songs)
            if candidate is current_song
        )
        self._history = []
        self._forward_history = []
        self._reset_shuffle_remaining()
        return self.current

    def clear(self) -> None:
        self.songs = []
        self.current_index = -1
        self._history = []
        self._forward_history = []
        self._shuffle_remaining = []

    def reorder(self, songs: list[Song]) -> Song | None:
        if sorted(map(id, songs)) != sorted(map(id, self.songs)):
            raise ValueError("Die neue Reihenfolge muss dieselben Titel enthalten.")
        current_song = self.current
        self.songs = list(songs)
        self.current_index = next(
            (
                position
                for position, song in enumerate(self.songs)
                if song is current_song
            ),
            -1,
        )
        self._history = []
        self._forward_history = []
        self._reset_shuffle_remaining()
        return self.current

    def extend(self, songs: list[Song]) -> int:
        additions = list(songs)
        self.songs.extend(additions)
        self._history = []
        self._forward_history = []
        self._reset_shuffle_remaining()
        return len(additions)

    def next(self, *, automatic: bool = False) -> Song | None:
        if automatic and self.repeat_mode == "one":
            return self.current
        if self.shuffle_mode == "fresh":
            return self._fresh_random()
        if self.shuffle_mode == "history" and self._forward_history:
            self._history.append(self.current_index)
            self.current_index = self._forward_history.pop()
            if self.current_index in self._shuffle_remaining:
                self._shuffle_remaining.remove(self.current_index)
            return self.current
        if self.shuffle:
            if not self._shuffle_remaining:
                if self.repeat_mode != "all":
                    return None
                self._reset_shuffle_remaining()
            if not self._shuffle_remaining:
                return self.current if self.repeat_mode == "all" else None
            self._history.append(self.current_index)
            self._forward_history = []
            self.current_index = random.choice(self._shuffle_remaining)
            self._shuffle_remaining.remove(self.current_index)
            return self.current
        if self.current_index + 1 >= len(self.songs):
            if self.repeat_mode == "all" and self.songs:
                self._history.append(self.current_index)
                self.current_index = 0
                return self.current
            return None
        self._history.append(self.current_index)
        self.current_index += 1
        return self.current

    def previous(self) -> Song | None:
        if self.shuffle_mode == "fresh":
            return self._fresh_random()
        if self.shuffle and self._history:
            if self.current_index >= 0:
                self._forward_history.append(self.current_index)
            self.current_index = self._history.pop()
            return self.current
        if self.current_index <= 0:
            if self.repeat_mode == "all" and self.songs:
                self.current_index = len(self.songs) - 1
                return self.current
            return None
        self.current_index -= 1
        return self.current

    def _fresh_random(self) -> Song | None:
        if len(self.songs) <= 1:
            return self.current
        if not self._shuffle_remaining:
            self._reset_shuffle_remaining()
        if not self._shuffle_remaining:
            return self.current
        self.current_index = random.choice(self._shuffle_remaining)
        self._shuffle_remaining.remove(self.current_index)
        return self.current

    def _reset_shuffle_remaining(self) -> None:
        self._shuffle_remaining = [
            index
            for index in range(len(self.songs))
            if index != self.current_index
        ]


def format_milliseconds(value: int) -> str:
    seconds = max(0, int(value)) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"
