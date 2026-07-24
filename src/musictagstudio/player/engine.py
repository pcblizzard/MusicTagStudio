from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from ..models.song import Song
from .model import PlaybackQueue


class PlayerEngine(QObject):
    song_changed = Signal(object)
    playback_changed = Signal(bool)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    error_occurred = Signal(str)
    queue_changed = Signal(object, int)
    repeat_changed = Signal(str)
    shuffle_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.queue = PlaybackQueue()
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.7)
        self.media_player = QMediaPlayer(self)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.positionChanged.connect(self.position_changed.emit)
        self.media_player.durationChanged.connect(self.duration_changed.emit)
        self.media_player.playbackStateChanged.connect(
            self._playback_state_changed
        )
        self.media_player.mediaStatusChanged.connect(self._media_status_changed)
        self.media_player.errorOccurred.connect(self._player_error)

    @property
    def current_song(self) -> Song | None:
        return self.queue.current

    def set_queue(
        self,
        songs: list[Song],
        start_index: int = 0,
        *,
        autoplay: bool = True,
    ) -> bool:
        song = self.queue.replace(songs, start_index)
        self.queue_changed.emit(list(self.queue.songs), self.queue.current_index)
        if self._load_song(song, autoplay=autoplay):
            return True
        return bool(song) and self._load_available("next", autoplay=autoplay)

    def toggle(self) -> None:
        if self.current_song is None:
            return
        if (
            self.media_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            self.media_player.pause()
        else:
            self.media_player.play()

    def next(self) -> bool:
        return self._load_available("next", autoplay=True)

    def previous(self) -> bool:
        if self.media_player.position() > 3000:
            self.media_player.setPosition(0)
            return True
        return self._load_available("previous", autoplay=True)

    def play_index(self, index: int) -> bool:
        return self._load_song(self.queue.play(index), autoplay=True)

    def remove_queue_index(self, index: int) -> None:
        removed_current = index == self.queue.current_index
        song = self.queue.remove(index)
        self.queue_changed.emit(list(self.queue.songs), self.queue.current_index)
        if removed_current:
            if song is None:
                self.stop()
                self.song_changed.emit(None)
            else:
                self._load_song(song, autoplay=True)

    def play_next(self, index: int) -> None:
        self.queue.move_next(index)
        self.queue_changed.emit(list(self.queue.songs), self.queue.current_index)

    def clear_queue(self) -> None:
        self.queue.clear()
        self.stop()
        self.song_changed.emit(None)
        self.queue_changed.emit([], -1)

    def reorder_queue(self, songs: list[Song]) -> None:
        self.queue.reorder(songs)
        self.queue_changed.emit(list(self.queue.songs), self.queue.current_index)

    def remove_queue_indices(self, indices: list[int]) -> None:
        for index in sorted(set(indices), reverse=True):
            self.remove_queue_index(index)

    def enqueue_songs(self, songs: list[Song]) -> int:
        additions = list(songs)
        if not additions:
            return 0
        if not self.queue.songs:
            self.set_queue(additions, 0, autoplay=False)
            return len(additions)
        count = self.queue.extend(additions)
        self.queue_changed.emit(list(self.queue.songs), self.queue.current_index)
        return count

    def cycle_shuffle(self) -> str:
        mode = self.queue.cycle_shuffle()
        self.shuffle_changed.emit(mode)
        return mode

    def cycle_repeat(self) -> str:
        mode = self.queue.cycle_repeat()
        self.repeat_changed.emit(mode)
        return mode

    def seek(self, position_ms: int) -> None:
        self.media_player.setPosition(max(0, int(position_ms)))

    def set_volume(self, percent: int) -> None:
        self.audio_output.setVolume(max(0, min(100, int(percent))) / 100)

    def toggle_mute(self) -> None:
        self.audio_output.setMuted(not self.audio_output.isMuted())

    def stop(self) -> None:
        self.media_player.stop()

    def _load_song(self, song: Song | None, *, autoplay: bool) -> bool:
        if song is None:
            return False
        path = Path(song.path)
        if not path.is_file():
            self.error_occurred.emit(f"Audiodatei nicht gefunden: {path}")
            return False
        self.media_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.song_changed.emit(song)
        self.queue_changed.emit(list(self.queue.songs), self.queue.current_index)
        if autoplay:
            self.media_player.play()
        return True

    def _load_available(self, direction: str, *, autoplay: bool) -> bool:
        attempts = max(1, len(self.queue.songs))
        for _ in range(attempts):
            song = (
                self.queue.previous()
                if direction == "previous"
                else self.queue.next()
            )
            if song is None:
                return False
            if self._load_song(song, autoplay=autoplay):
                return True
        return False

    def _playback_state_changed(self, state) -> None:
        self.playback_changed.emit(
            state == QMediaPlayer.PlaybackState.PlayingState
        )

    def _media_status_changed(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            song = self.queue.next(automatic=True)
            if not self._load_song(song, autoplay=True) and not self._load_available(
                "next", autoplay=True
            ):
                self.playback_changed.emit(False)

    def _player_error(self, _error, message: str) -> None:
        self.error_occurred.emit(message or "Die Audiodatei konnte nicht abgespielt werden.")
