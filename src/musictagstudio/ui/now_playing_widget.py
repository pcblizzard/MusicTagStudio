from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..models.song import Song


def _time(ms: int) -> str:
    seconds = max(0, ms) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


class _BpmSignals(QObject):
    done = Signal(str, object)  # path, bpm|None


class _BpmTask(QRunnable):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        self.signals = _BpmSignals()

    @Slot()
    def run(self) -> None:
        try:
            from ..audio_analysis.bpm import detect_bpm

            self.signals.done.emit(self.path, detect_bpm(self.path))
        except Exception:  # noqa: BLE001
            self.signals.done.emit(self.path, None)


class NowPlayingWidget(QWidget):
    """Große Wiedergabe-Ansicht: Cover, Titel/Album/Künstler, BPM, Steuerung."""

    detach_requested = Signal()
    stats_requested = Signal()

    def __init__(
        self,
        engine,
        parent=None,
        *,
        language: str = "automatic",
        allow_detach: bool = True,
        favorites=None,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.engine = engine
        self.favorites = favorites
        self._current_path = ""
        self._bpm_pool = QThreadPool(self)
        self._bpm_pool.setMaxThreadCount(1)
        self._bpm_path = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        top = QHBoxLayout()
        self.favorite_button = QPushButton("♡")
        self.favorite_button.setToolTip(tr("favorite_toggle_tip", language))
        self.favorite_button.setFixedWidth(44)
        self.favorite_button.clicked.connect(self._toggle_favorite)
        self.favorite_button.setEnabled(favorites is not None)
        top.addWidget(self.favorite_button)

        self.stats_button = QPushButton("📊 " + tr("stats_title", language))
        self.stats_button.clicked.connect(self.stats_requested.emit)
        top.addWidget(self.stats_button)

        top.addStretch(1)
        if allow_detach:
            detach = QPushButton("⧉ " + tr("now_playing_detach", language))
            detach.clicked.connect(self.detach_requested.emit)
            top.addWidget(detach)
        layout.addLayout(top)

        self.cover = QLabel()
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setMinimumHeight(280)
        self.cover.setStyleSheet(
            "background: palette(dark); border-radius: 8px; color: palette(mid);"
        )
        layout.addWidget(self.cover, 1)

        self.title = QLabel("")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-size: 20px; font-weight: 600;")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)

        self.artist = QLabel("")
        self.artist.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.artist.setStyleSheet("font-size: 14px; color: palette(mid);")
        layout.addWidget(self.artist)

        self.details = QLabel("")
        self.details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.details.setStyleSheet("color: palette(mid);")
        layout.addWidget(self.details)

        self.bpm_label = QLabel("")
        self.bpm_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bpm_label.setStyleSheet("color: palette(mid);")
        layout.addWidget(self.bpm_label)

        seek_row = QHBoxLayout()
        self.position_label = QLabel("0:00")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.engine.seek)
        self.duration_label = QLabel("0:00")
        seek_row.addWidget(self.position_label)
        seek_row.addWidget(self.slider, 1)
        seek_row.addWidget(self.duration_label)
        layout.addLayout(seek_row)

        controls = QHBoxLayout()
        controls.addStretch(1)
        self.prev_button = QPushButton("⏮")
        self.prev_button.clicked.connect(self.engine.previous)
        self.play_button = QPushButton("▶")
        self.play_button.clicked.connect(self.engine.toggle)
        self.next_button = QPushButton("⏭")
        self.next_button.clicked.connect(self.engine.next)
        for button in (self.prev_button, self.play_button, self.next_button):
            button.setFixedWidth(60)
            controls.addWidget(button)
        controls.addStretch(1)
        layout.addLayout(controls)

        engine.song_changed.connect(self._on_song)
        engine.playback_changed.connect(self._on_playback)
        engine.position_changed.connect(self._on_position)
        engine.duration_changed.connect(self._on_duration)

        self._on_song(engine.current_song)

    # --- Engine-Updates -----------------------------------------------------

    def _on_song(self, song: Song | None) -> None:
        self._current_path = song.path if song is not None else ""
        self._update_favorite_button()
        if song is None:
            self.title.setText(tr("now_playing_none", self.language))
            self.artist.setText("")
            self.details.setText("")
            self.bpm_label.setText("")
            self.cover.setText("♪")
            self.cover.setPixmap(QPixmap())
            self.slider.setRange(0, 0)
            return
        from pathlib import Path

        self.title.setText(song.title or Path(song.path).name)
        self.artist.setText(song.artist or song.album_artist or "")
        parts = [p for p in (song.album, song.year, song.genre) if p]
        self.details.setText(" · ".join(parts))
        self._load_cover(song.path)
        self._start_bpm(song.path)

    def _on_playback(self, playing: bool) -> None:
        self.play_button.setText("⏸" if playing else "▶")

    def _toggle_favorite(self) -> None:
        if self.favorites is None or not self._current_path:
            return
        self.favorites.toggle("song", self._current_path)
        self._update_favorite_button()

    def _update_favorite_button(self) -> None:
        if self.favorites is None or not self._current_path:
            self.favorite_button.setText("♡")
            self.favorite_button.setEnabled(False)
            return
        self.favorite_button.setEnabled(True)
        is_fav = self.favorites.is_favorite("song", self._current_path)
        self.favorite_button.setText("♥" if is_fav else "♡")
        self.favorite_button.setStyleSheet(
            "color: #e53935; font-size: 16px;" if is_fav else "font-size: 16px;"
        )

    def _on_position(self, position_ms: int) -> None:
        if not self.slider.isSliderDown():
            self.slider.setValue(position_ms)
        self.position_label.setText(_time(position_ms))

    def _on_duration(self, duration_ms: int) -> None:
        self.slider.setRange(0, max(0, duration_ms))
        self.duration_label.setText(_time(duration_ms))

    # --- Cover & BPM --------------------------------------------------------

    def _load_cover(self, path: str) -> None:
        try:
            from ..services.cover import load_cover

            data = load_cover(path)
        except Exception:  # noqa: BLE001
            data = None
        if not data:
            self.cover.setText("♪")
            self.cover.setPixmap(QPixmap())
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.cover.setPixmap(
                pixmap.scaled(
                    360, 360,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.cover.setText("♪")

    def _start_bpm(self, path: str) -> None:
        self._bpm_path = path
        self.bpm_label.setText(tr("now_playing_bpm_wait", self.language))
        task = _BpmTask(path)
        task.signals.done.connect(self._on_bpm)
        self._bpm_pool.start(task)

    def _on_bpm(self, path: str, bpm) -> None:
        if path != self._bpm_path:
            return  # veraltetes Ergebnis (Titel gewechselt)
        self.bpm_label.setText(
            tr("now_playing_bpm", self.language, bpm=bpm) if bpm else ""
        )
