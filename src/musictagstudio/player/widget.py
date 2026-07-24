from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..models.song import Song
from .engine import PlayerEngine
from .model import format_milliseconds
from .queue_dialog import QueueDialog
from ..services.cover import load_cover


class PlayerBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.engine = PlayerEngine(self)
        self.queue_dialog: QueueDialog | None = None
        self.settings = QSettings("MusicTagStudio", "MusicTagStudio")
        self.engine.queue.repeat_mode = str(
            self.settings.value("player/repeat_mode", "off")
        )
        if self.engine.queue.repeat_mode not in {"off", "all", "one"}:
            self.engine.queue.repeat_mode = "off"
        self.engine.queue.shuffle_mode = str(
            self.settings.value("player/shuffle_mode", "off")
        )
        if self.engine.queue.shuffle_mode not in {"off", "history", "fresh"}:
            self.engine.queue.shuffle_mode = "off"
        self._seeking = False
        self.setObjectName("playerBar")
        self.setStyleSheet(
            "QWidget#playerBar { border-top: 1px solid palette(mid); }"
            "QPushButton[active=\"true\"] {"
            "background: palette(highlight); color: palette(highlighted-text);"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(42, 42)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet(
            "border: 1px solid palette(mid); background: palette(base);"
        )
        self.shuffle_button = QPushButton("🔀")
        self.previous_button = QPushButton("◀")
        self.play_button = QPushButton("▶")
        self.next_button = QPushButton("▶|")
        self.repeat_button = QPushButton("↻")
        self.queue_button = QPushButton("☷")
        self.shuffle_button.setToolTip("Zufallswiedergabe: Aus")
        self.previous_button.setToolTip("Vorheriger Titel")
        self.play_button.setToolTip("Wiedergabe/Pause")
        self.next_button.setToolTip("Nächster Titel")
        self.repeat_button.setToolTip("Wiederholen: Aus")
        self.queue_button.setToolTip("Warteschlange anzeigen")
        self.shuffle_button.setAccessibleName("Zufallswiedergabe")
        self.previous_button.setAccessibleName("Vorheriger Titel")
        self.play_button.setAccessibleName("Wiedergabe oder Pause")
        self.next_button.setAccessibleName("Nächster Titel")
        self.repeat_button.setAccessibleName("Wiederholungsmodus")
        self.queue_button.setAccessibleName("Warteschlange")
        self.title_label = QLabel("Kein Titel geladen")
        self.title_label.setMinimumWidth(150)
        self.album_label = QLabel("")
        self.album_label.setStyleSheet("color: palette(mid);")
        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.album_label)
        self.position_label = QLabel("0:00")
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.duration_label = QLabel("0:00")
        self.volume_label = QLabel("Lautstärke")
        self.mute_button = QPushButton("🔊")
        self.mute_button.setToolTip("Stummschaltung")
        self.mute_button.setFixedWidth(38)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        try:
            saved_volume = int(self.settings.value("player/volume", 70))
        except (TypeError, ValueError):
            saved_volume = 70
        self.volume_slider.setValue(max(0, min(100, saved_volume)))
        self.volume_slider.setMaximumWidth(110)

        layout.addWidget(self.cover_label)
        for widget in (
            self.shuffle_button,
            self.previous_button,
            self.play_button,
            self.next_button,
            self.repeat_button,
        ):
            widget.setFixedWidth(38)
            layout.addWidget(widget)
        layout.addLayout(title_layout)
        layout.addWidget(self.position_label)
        layout.addWidget(self.position_slider, stretch=1)
        layout.addWidget(self.duration_label)
        self.queue_button.setFixedWidth(42)
        layout.addWidget(self.queue_button)
        layout.addWidget(self.volume_label)
        layout.addWidget(self.mute_button)
        layout.addWidget(self.volume_slider)

        self.previous_button.clicked.connect(self.engine.previous)
        self.play_button.clicked.connect(self.engine.toggle)
        self.next_button.clicked.connect(self.engine.next)
        self.shuffle_button.clicked.connect(self.engine.cycle_shuffle)
        self.repeat_button.clicked.connect(self.engine.cycle_repeat)
        self.queue_button.clicked.connect(self._show_queue_dialog)
        self.mute_button.clicked.connect(self.engine.toggle_mute)
        self.volume_slider.valueChanged.connect(self._volume_changed)
        self.engine.audio_output.mutedChanged.connect(self._muted_changed)
        self.position_slider.sliderPressed.connect(self._seek_started)
        self.position_slider.sliderReleased.connect(self._seek_finished)
        self.engine.song_changed.connect(self._song_changed)
        self.engine.playback_changed.connect(self._playback_changed)
        self.engine.position_changed.connect(self._position_changed)
        self.engine.duration_changed.connect(self._duration_changed)
        self.engine.error_occurred.connect(self._show_error)
        self.engine.queue_changed.connect(self._queue_changed)
        self.engine.repeat_changed.connect(self._repeat_changed)
        self.engine.shuffle_changed.connect(self._shuffle_changed)
        self._repeat_changed(self.engine.queue.repeat_mode)
        self._shuffle_changed(self.engine.queue.shuffle_mode)
        self.engine.set_volume(self.volume_slider.value())
        saved_muted = str(
            self.settings.value("player/muted", "false")
        ).casefold() in {"1", "true", "yes"}
        self.engine.audio_output.setMuted(saved_muted)
        self._muted_changed(saved_muted)

    def play_songs(self, songs: list[Song], start_index: int = 0) -> bool:
        return self.engine.set_queue(songs, start_index, autoplay=True)

    def _song_changed(self, song: Song | None) -> None:
        if song is None:
            self.title_label.setText("Kein Titel geladen")
            self.album_label.clear()
            self.cover_label.clear()
            self.cover_label.setText("♪")
            self.position_slider.setRange(0, 0)
            self.position_label.setText("0:00")
            self.duration_label.setText("0:00")
            return
        detail = song.artist or song.album_artist
        self.title_label.setText(
            f"{song.title} - {detail}" if detail else song.title
        )
        self.album_label.setText(song.album)
        self.title_label.setToolTip(str(song.path))
        self._show_song_cover(song)

    def _playback_changed(self, playing: bool) -> None:
        self.play_button.setText("Ⅱ" if playing else "▶")

    def _position_changed(self, position: int) -> None:
        self.position_label.setText(format_milliseconds(position))
        if not self._seeking:
            self.position_slider.setValue(position)

    def _duration_changed(self, duration: int) -> None:
        self.position_slider.setRange(0, max(0, duration))
        self.duration_label.setText(format_milliseconds(duration))

    def _muted_changed(self, muted: bool) -> None:
        self.mute_button.setText("🔇" if muted else "🔊")
        self.mute_button.setToolTip(
            "Ton einschalten" if muted else "Stummschalten"
        )
        self.settings.setValue("player/muted", muted)

    def _repeat_changed(self, mode: str) -> None:
        labels = {
            "off": ("↻", "Wiederholen: Aus"),
            "all": ("↻", "Wiederholen: Album/Warteschlange"),
            "one": ("↻¹", "Wiederholen: Aktueller Titel"),
        }
        text, tooltip = labels.get(mode, labels["off"])
        self.repeat_button.setText(text)
        self.repeat_button.setToolTip(tooltip)
        self.repeat_button.setProperty("active", mode != "off")
        self.settings.setValue("player/repeat_mode", mode)
        self.repeat_button.style().unpolish(self.repeat_button)
        self.repeat_button.style().polish(self.repeat_button)

    def _shuffle_changed(self, mode: str) -> None:
        labels = {
            "off": ("🔀", "Zufallswiedergabe: Aus"),
            "history": ("🔀", "Zufallswiedergabe: Mit Verlauf"),
            "fresh": ("🎲", "Zufallswiedergabe: Immer neu auslosen"),
        }
        text, tooltip = labels.get(mode, labels["off"])
        self.shuffle_button.setText(text)
        self.shuffle_button.setProperty("active", mode != "off")
        self.shuffle_button.setToolTip(tooltip)
        self.settings.setValue("player/shuffle_mode", mode)
        self.shuffle_button.style().unpolish(self.shuffle_button)
        self.shuffle_button.style().polish(self.shuffle_button)

    def _queue_changed(self, songs: list[Song], current_index: int) -> None:
        count = len(songs)
        self.queue_button.setToolTip(
            f"Warteschlange anzeigen ({count} Titel)"
            if count != 1
            else "Warteschlange anzeigen (1 Titel)"
        )

    def _show_queue_dialog(self) -> None:
        if self.queue_dialog is None:
            self.queue_dialog = QueueDialog(self.engine, self)
        self.queue_dialog.show()
        self.queue_dialog.raise_()
        self.queue_dialog.activateWindow()

    def _show_song_cover(self, song: Song) -> None:
        data = song.cover
        if not data and song.path:
            try:
                data = load_cover(song.path)
            except Exception:
                data = None
        pixmap = QPixmap()
        if not data or not pixmap.loadFromData(data):
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("♪")
            return
        size = self.cover_label.size()
        scaled = pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - size.width()) // 2)
        y = max(0, (scaled.height() - size.height()) // 2)
        self.cover_label.setText("")
        self.cover_label.setPixmap(
            scaled.copy(x, y, size.width(), size.height())
        )

    def _seek_started(self) -> None:
        self._seeking = True

    def _seek_finished(self) -> None:
        self._seeking = False
        self.engine.seek(self.position_slider.value())

    def _volume_changed(self, value: int) -> None:
        self.engine.set_volume(value)
        self.settings.setValue("player/volume", value)

    def _show_error(self, message: str) -> None:
        self.title_label.setText(message)
        self.play_button.setText("▶")
