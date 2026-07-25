from __future__ import annotations

import os
import tempfile
from urllib.request import Request, urlopen

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from .. import __version__


# Die Vorschau-CDNs (Apple/Deezer) weisen den Standard-User-Agent von
# Qts ffmpeg-Backend ("Lavf…") mit HTTP 403 ab. Deshalb wird die Datei mit
# einem Browser-User-Agent selbst geladen und lokal abgespielt.
PREVIEW_USER_AGENT = (
    f"Mozilla/5.0 (compatible; MusicTagStudio/{__version__})"
)
DOWNLOAD_TIMEOUT_SECONDS = 15


def _download_preview(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": PREVIEW_USER_AGENT,
            "Accept": "*/*",
        },
    )
    with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        return response.read()


class _DownloadSignals(QObject):
    done = Signal(int, str, bytes)
    failed = Signal(int, str)


class _DownloadWorker(QRunnable):
    def __init__(self, token: int, url: str) -> None:
        super().__init__()
        self._token = token
        self._url = url
        self.signals = _DownloadSignals()

    @Slot()
    def run(self) -> None:
        try:
            data = _download_preview(self._url)
        except Exception as error:  # noqa: BLE001 - Netzwerkfehler nicht fatal
            self.signals.failed.emit(self._token, str(error))
            return

        self.signals.done.emit(self._token, self._url, data)


class PreviewPlayer(QObject):
    """Spielt einzelne 30-Sekunden-Vorschauen (Apple/Deezer) ab.

    Die Datei wird zuerst mit einem Browser-User-Agent in eine temporäre
    Datei geladen (die CDNs blockieren den ffmpeg-User-Agent von Qt) und
    anschließend lokal abgespielt. Bewusst getrennt vom Haupt-PlayerEngine,
    damit die Wiedergabe-Queue der lokalen Bibliothek unberührt bleibt.

    Es läuft immer nur eine Vorschau; eine neue ersetzt die vorherige.
    Das Signal state_changed(url, is_playing) hält die Oberfläche aktuell.
    """

    state_changed = Signal(str, bool)
    error_occurred = Signal(str)
    # Für die Wiedergabe-Leiste: eine Vorschau-Sitzung ist aktiv (True) bzw.
    # beendet (False), sowie laufende Position/Dauer in Millisekunden.
    session_changed = Signal(bool)
    position_changed = Signal(int)
    duration_changed = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._audio_output = QAudioOutput(self)
        self._audio_output.setVolume(0.8)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        self._current_url = ""
        self._current_title = ""
        self._active = False
        self._token = 0
        self._temp_path = ""
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.mediaStatusChanged.connect(self._on_status_changed)
        self._player.errorOccurred.connect(self._on_error)
        self._player.positionChanged.connect(self.position_changed.emit)
        self._player.durationChanged.connect(self.duration_changed.emit)

    @property
    def current_url(self) -> str:
        return self._current_url

    @property
    def current_title(self) -> str:
        return self._current_title

    @property
    def is_active(self) -> bool:
        """True, sobald eine Vorschau angefordert wurde, bis sie endet."""
        return self._active

    def is_playing(self) -> bool:
        return (
            self._player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        )

    def toggle(self, url: str) -> None:
        """Startet die Vorschau – oder stoppt sie, wenn sie bereits läuft."""
        url = (url or "").strip()

        if not url:
            return

        if url == self._current_url and self.is_playing():
            self.stop()
            return

        self.play(url)

    def play(self, url: str, title: str = "") -> None:
        url = (url or "").strip()

        if not url:
            return

        self._current_url = url
        self._current_title = title
        # Token invalidiert noch laufende Downloads einer früheren Vorschau.
        self._token += 1
        self._player.stop()

        if not self._active:
            self._active = True
            self.session_changed.emit(True)

        worker = _DownloadWorker(self._token, url)
        worker.signals.done.connect(self._on_downloaded)
        worker.signals.failed.connect(self._on_download_failed)
        self._pool.start(worker)

    def toggle_pause(self) -> None:
        """Pausiert bzw. setzt die laufende Vorschau fort (ohne Neuladen)."""
        state = self._player.playbackState()

        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._player.play()

    def seek(self, position_ms: int) -> None:
        self._player.setPosition(max(0, int(position_ms)))

    def stop(self) -> None:
        self._token += 1
        self._player.stop()
        self._end_session()

    def _end_session(self) -> None:
        if self._active:
            self._active = False
            self.session_changed.emit(False)

    def set_volume(self, percent: int) -> None:
        self._audio_output.setVolume(max(0, min(100, int(percent))) / 100)

    def _on_downloaded(self, token: int, url: str, data: bytes) -> None:
        if token != self._token:
            return

        previous = self._temp_path
        path = self._write_temp(bytes(data), url)

        if not path:
            self.error_occurred.emit(
                "Die Vorschau konnte nicht zwischengespeichert werden."
            )
            return

        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

        # Die vorherige Temp-Datei ist jetzt nicht mehr die Quelle und kann
        # gefahrlos entfernt werden.
        _safe_remove(previous)

    def _on_download_failed(self, token: int, _message: str) -> None:
        if token != self._token:
            return

        self.error_occurred.emit(
            "Die Vorschau konnte nicht geladen werden."
        )
        self._end_session()

    def _write_temp(self, data: bytes, url: str) -> str:
        suffix = ".m4a" if ("m4a" in url or "AudioPreview" in url) else ".mp3"

        try:
            handle, path = tempfile.mkstemp(
                prefix="mts_preview_",
                suffix=suffix,
            )
            with os.fdopen(handle, "wb") as file:
                file.write(data)
        except OSError:
            return ""

        self._temp_path = path
        return path

    def _on_state_changed(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.state_changed.emit(self._current_url, playing)

    def _on_status_changed(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.stop()

    def _on_error(self, _error, message: str) -> None:
        self.error_occurred.emit(
            message or "Die Vorschau konnte nicht abgespielt werden."
        )


def _safe_remove(path: str) -> None:
    if not path:
        return

    try:
        os.remove(path)
    except OSError:
        # Unter Windows kann die Datei kurzzeitig noch gesperrt sein; sie
        # landet dann ohnehin im Temp-Verzeichnis des Systems.
        pass
