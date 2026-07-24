from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, Signal

from ..models.song import Song
from ..services.cover import load_cover
from .engine import PlayerEngine


LOGGER = logging.getLogger(__name__)


def system_media_metadata(song: Song) -> dict[str, str]:
    return {
        "title": song.title or Path(song.path).stem,
        "artist": song.artist or song.album_artist,
        "album": song.album,
        "album_artist": song.album_artist or song.artist,
    }


class WindowsSystemMediaBridge(QObject):
    toggle_requested = Signal()
    next_requested = Signal()
    previous_requested = Signal()
    stop_requested = Signal()

    def __init__(self, engine: PlayerEngine, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self._media_player = None
        self._controls = None
        self._button_token = None
        self._media = None
        self._streams = None
        self._foundation = None
        self._available = False
        self.toggle_requested.connect(engine.toggle)
        self.next_requested.connect(engine.next)
        self.previous_requested.connect(engine.previous)
        self.stop_requested.connect(engine.stop)

    @property
    def available(self) -> bool:
        return self._available

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            from winrt.windows import foundation, media
            from winrt.windows.media import playback
            from winrt.windows.storage import streams

            self._media = media
            self._streams = streams
            self._foundation = foundation
            self._media_player = playback.MediaPlayer()
            self._controls = self._media_player.system_media_transport_controls
            self._configure_controls()
            self._button_token = self._controls.add_button_pressed(
                self._button_pressed
            )
            self.engine.song_changed.connect(self.update_song)
            self.engine.playback_changed.connect(self.update_playback)
            self._available = True
            if self.engine.current_song is not None:
                self.update_song(self.engine.current_song)
            return True
        except (ImportError, OSError, RuntimeError) as error:
            LOGGER.warning(
                "Windows-Systemmedienanzeige ist nicht verfügbar: %s",
                error,
            )
            self.stop()
            return False

    def stop(self) -> None:
        try:
            self.engine.song_changed.disconnect(self.update_song)
        except (RuntimeError, TypeError):
            pass
        try:
            self.engine.playback_changed.disconnect(self.update_playback)
        except (RuntimeError, TypeError):
            pass
        if self._controls is not None:
            try:
                if self._button_token is not None:
                    self._controls.remove_button_pressed(self._button_token)
                self._controls.playback_status = (
                    self._media.MediaPlaybackStatus.CLOSED
                )
                self._controls.display_updater.clear_all()
                self._controls.display_updater.update()
                self._controls.is_enabled = False
            except (OSError, RuntimeError):
                pass
        if self._media_player is not None:
            try:
                self._media_player.close()
            except (OSError, RuntimeError):
                pass
        self._media_player = None
        self._controls = None
        self._button_token = None
        self._available = False

    def update_song(self, song: Song | None) -> None:
        if not self._available or self._controls is None:
            return
        try:
            updater = self._controls.display_updater
            updater.clear_all()
            if song is None:
                updater.update()
                self._controls.playback_status = (
                    self._media.MediaPlaybackStatus.STOPPED
                )
                return
            updater.type = self._media.MediaPlaybackType.MUSIC
            metadata = system_media_metadata(song)
            properties = updater.music_properties
            properties.title = metadata["title"]
            properties.artist = metadata["artist"]
            properties.album_title = metadata["album"]
            properties.album_artist = metadata["album_artist"]
            thumbnail = self._cover_reference(song)
            if thumbnail is not None:
                updater.thumbnail = thumbnail
            updater.update()
        except (OSError, RuntimeError, ValueError) as error:
            LOGGER.warning(
                "Windows-Medieninformationen konnten nicht aktualisiert werden: %s",
                error,
            )

    def update_playback(self, playing: bool) -> None:
        if not self._available or self._controls is None:
            return
        try:
            self._controls.playback_status = (
                self._media.MediaPlaybackStatus.PLAYING
                if playing
                else self._media.MediaPlaybackStatus.PAUSED
            )
        except (OSError, RuntimeError):
            pass

    def _configure_controls(self) -> None:
        self._controls.is_enabled = True
        self._controls.is_play_enabled = True
        self._controls.is_pause_enabled = True
        self._controls.is_next_enabled = True
        self._controls.is_previous_enabled = True
        self._controls.is_stop_enabled = True
        self._controls.playback_status = self._media.MediaPlaybackStatus.STOPPED

    def _button_pressed(self, _sender, args) -> None:
        button = args.button
        buttons = self._media.SystemMediaTransportControlsButton
        if button in {buttons.PLAY, buttons.PAUSE}:
            self.toggle_requested.emit()
        elif button == buttons.NEXT:
            self.next_requested.emit()
        elif button == buttons.PREVIOUS:
            self.previous_requested.emit()
        elif button == buttons.STOP:
            self.stop_requested.emit()

    def _cover_reference(self, song: Song):
        data = song.cover
        if not data and song.path:
            try:
                data = load_cover(song.path)
            except (OSError, ValueError):
                data = None
        if not data:
            return None
        cache_root = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.CacheLocation
        )
        destination = Path(cache_root) / "system-media"
        destination.mkdir(parents=True, exist_ok=True)
        suffix = ".png" if data.startswith(b"\x89PNG") else ".jpg"
        cover_path = destination / (
            hashlib.sha256(data).hexdigest() + suffix
        )
        if not cover_path.is_file():
            cover_path.write_bytes(data)
        uri = self._foundation.Uri(cover_path.resolve().as_uri())
        return self._streams.RandomAccessStreamReference.create_from_uri(uri)
