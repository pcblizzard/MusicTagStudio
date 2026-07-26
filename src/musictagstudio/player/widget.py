from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, QSize, Qt, Signal
from PySide6.QtGui import QPalette, QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..models.song import Song
from ..icons import make_icon
from .engine import PlayerEngine
from .model import (
    QUEUE_PERSIST_LIMIT,
    format_milliseconds,
    song_from_dict,
    song_to_dict,
)
from .queue_dialog import QueueDialog
from ..services.cover import load_cover


logger = logging.getLogger(__name__)

# Anzeigedauer transienter Player-Fehlermeldungen in der App-Statusleiste.
PLAYER_ERROR_TIMEOUT_MS = 6000


class PlayerBar(QWidget):
    # Einheitlicher Fehler-/Statuskanal: die Leiste meldet transiente Fehler
    # (z. B. nicht abspielbare Datei) an die App, die sie in der Statusleiste
    # anzeigt – statt den angezeigten Titel zu überschreiben.
    status_requested = Signal(str, int)

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
        # Wenn eine 30-Sekunden-Vorschau läuft, übernimmt die Leiste vorüber-
        # gehend deren Anzeige und Steuerung, ohne die lokale Warteschlange zu
        # verändern (die lokale Wiedergabe wird nur pausiert).
        self._preview_mode = False
        self.preview_player: object | None = None
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
        self.shuffle_button = QPushButton()
        self.previous_button = QPushButton()
        self.play_button = QPushButton()
        self.next_button = QPushButton()
        self.repeat_button = QPushButton()
        self.queue_button = QPushButton()
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
        self.mute_button = QPushButton()
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
        layout.addWidget(self.mute_button)
        layout.addWidget(self.volume_slider)

        self.previous_button.clicked.connect(self.engine.previous)
        self.play_button.clicked.connect(self._toggle_play)
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
        self._apply_icons()
        self._icons_ready = True
        self.restore_queue()

    # -- Warteschlange speichern/wiederherstellen ----------------------------

    def save_queue(self) -> None:
        """Speichert die aktuelle Warteschlange (Songs + Index) beim Beenden."""
        songs = self.engine.queue.songs[:QUEUE_PERSIST_LIMIT]
        if not songs:
            self.settings.remove("player/queue")
            return
        index = self.engine.queue.current_index
        if index >= len(songs):
            index = -1
        payload = {
            "songs": [song_to_dict(song) for song in songs],
            "current_index": index,
        }
        self.settings.setValue("player/queue", json.dumps(payload))

    def restore_queue(self) -> None:
        """Stellt die gespeicherte Warteschlange wieder her (pausiert).

        Nicht mehr vorhandene Dateien werden übersprungen; es wird bewusst
        nichts automatisch abgespielt.
        """
        raw = self.settings.value("player/queue", "")
        if not raw:
            return
        try:
            payload = json.loads(str(raw))
            entries = payload.get("songs", [])
            saved_index = int(payload.get("current_index", -1))
        except (ValueError, TypeError, AttributeError):
            self.settings.remove("player/queue")
            return

        songs = []
        start_index = 0
        for position, entry in enumerate(entries):
            song = song_from_dict(entry)
            if not song.path or not Path(song.path).is_file():
                continue
            if position == saved_index:
                # Position des gespeicherten Titels in der gefilterten Liste.
                start_index = len(songs)
            songs.append(song)

        if not songs:
            return

        # autoplay=False: Die Queue wird nur geladen und angezeigt, nicht
        # gestartet – der Nutzer entscheidet, ob weitergehört wird.
        self.engine.set_queue(songs, start_index, autoplay=False)

    # -- Icons ---------------------------------------------------------------

    def _icon_color(self) -> str:
        return self.palette().color(QPalette.ColorRole.ButtonText).name()

    def _current_playing(self) -> bool:
        if self._preview_mode and self.preview_player is not None:
            return self.preview_player.is_playing()
        return (
            self.engine.media_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        )

    def _set_play_icon(self, playing: bool) -> None:
        self.play_button.setIcon(
            make_icon("pause" if playing else "play", self._icon_color())
        )

    def _set_repeat_icon(self, mode: str) -> None:
        name = "repeat_one" if mode == "one" else "repeat"
        self.repeat_button.setIcon(make_icon(name, self._icon_color()))

    def _set_shuffle_icon(self, mode: str | None = None) -> None:
        if mode is None:
            mode = self.engine.queue.shuffle_mode
        name = "shuffle_fresh" if mode == "fresh" else "shuffle"
        self.shuffle_button.setIcon(make_icon(name, self._icon_color()))

    def _set_mute_icon(self, muted: bool) -> None:
        self.mute_button.setIcon(
            make_icon("mute" if muted else "volume", self._icon_color())
        )

    def _apply_icons(self) -> None:
        """Setzt alle Icons in der aktuellen Palette-Farbe (auch bei Theme-
        Wechsel neu)."""
        size = QSize(18, 18)
        for button in (
            self.shuffle_button,
            self.previous_button,
            self.play_button,
            self.next_button,
            self.repeat_button,
            self.queue_button,
            self.mute_button,
        ):
            button.setIconSize(size)

        color = self._icon_color()
        self.previous_button.setIcon(make_icon("previous", color))
        self.next_button.setIcon(make_icon("next", color))
        self.queue_button.setIcon(make_icon("queue", color))
        self._set_play_icon(self._current_playing())
        self._set_repeat_icon(self.engine.queue.repeat_mode)
        self._set_shuffle_icon()
        self._set_mute_icon(self.engine.audio_output.isMuted())

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        # Kann während der Konstruktion feuern, bevor die Knöpfe existieren.
        if not getattr(self, "_icons_ready", False):
            return
        if event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
            QEvent.Type.ApplicationPaletteChange,
        ):
            self._apply_icons()

    def play_songs(self, songs: list[Song], start_index: int = 0) -> bool:
        return self.engine.set_queue(songs, start_index, autoplay=True)

    def bind_preview_player(self, player) -> None:
        """Verbindet die Leiste mit einem Vorschau-Player.

        Während einer Vorschau zeigt die Leiste Titel, Position und die
        ~30-Sekunden-Dauer der Vorschau an und steuert Wiedergabe/Pause sowie
        die Suchleiste für die Vorschau. Die lokale Warteschlange bleibt
        unangetastet und wird nach der Vorschau unverändert wiederhergestellt.
        """
        self.preview_player = player
        player.session_changed.connect(self._preview_session_changed)
        player.state_changed.connect(self._preview_state_changed)
        player.position_changed.connect(self._preview_position_changed)
        player.duration_changed.connect(self._preview_duration_changed)

    def _preview_session_changed(self, active: bool) -> None:
        self._preview_mode = active

        if active:
            # Zwei gleichzeitige Audiostreams vermeiden: lokale Wiedergabe
            # pausieren (Queue/Position bleiben erhalten).
            if (
                self.engine.media_player.playbackState()
                == QMediaPlayer.PlaybackState.PlayingState
            ):
                self.engine.media_player.pause()

            self._apply_preview_title()
            self.album_label.setText("30-Sekunden-Vorschau")
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("♪")
            self.position_slider.setRange(0, 0)
            self.position_label.setText("0:00")
            self.duration_label.setText("0:00")
            self._set_play_icon(True)
            self._set_queue_controls_enabled(False)

            if self.preview_player is not None:
                self.preview_player.set_volume(self.volume_slider.value())
        else:
            self._set_queue_controls_enabled(True)
            self._restore_engine_display()

    def _set_queue_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.shuffle_button,
            self.previous_button,
            self.next_button,
            self.repeat_button,
            self.queue_button,
        ):
            widget.setEnabled(enabled)

    def _restore_engine_display(self) -> None:
        self._song_changed(self.engine.current_song)
        self._playback_changed(
            self.engine.media_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        )
        self._duration_changed(self.engine.media_player.duration())
        self._position_changed(self.engine.media_player.position())

    def _apply_preview_title(self) -> None:
        title = (
            self.preview_player.current_title
            if self.preview_player is not None
            else ""
        ) or "Vorschau"
        self.title_label.setText(f"{title} (Vorschau)")
        self.title_label.setToolTip("30-Sekunden-Vorschau")

    def _preview_state_changed(self, _url: str, playing: bool) -> None:
        if self._preview_mode:
            self._set_play_icon(playing)
            # Beim Wechsel auf eine andere Vorschau bleibt die Sitzung aktiv,
            # daher wird der Titel hier (nicht nur bei Sitzungsbeginn)
            # aktualisiert, sobald die neue Vorschau spielt.
            if playing:
                self._apply_preview_title()

    def _preview_position_changed(self, position: int) -> None:
        if self._preview_mode:
            self.position_label.setText(format_milliseconds(position))
            if not self._seeking:
                self.position_slider.setValue(position)

    def _preview_duration_changed(self, duration: int) -> None:
        if self._preview_mode:
            self.position_slider.setRange(0, max(0, duration))
            self.duration_label.setText(format_milliseconds(duration))

    def _toggle_play(self) -> None:
        if self._preview_mode and self.preview_player is not None:
            self.preview_player.toggle_pause()
        else:
            self.engine.toggle()

    def _song_changed(self, song: Song | None) -> None:
        if self._preview_mode:
            return
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
        if self._preview_mode:
            return
        self._set_play_icon(playing)

    def _position_changed(self, position: int) -> None:
        if self._preview_mode:
            return
        self.position_label.setText(format_milliseconds(position))
        if not self._seeking:
            self.position_slider.setValue(position)

    def _duration_changed(self, duration: int) -> None:
        if self._preview_mode:
            return
        self.position_slider.setRange(0, max(0, duration))
        self.duration_label.setText(format_milliseconds(duration))

    def _muted_changed(self, muted: bool) -> None:
        self._set_mute_icon(muted)
        self.mute_button.setToolTip(
            "Ton einschalten" if muted else "Stummschalten"
        )
        self.settings.setValue("player/muted", muted)

    def _repeat_changed(self, mode: str) -> None:
        tooltips = {
            "off": "Wiederholen: Aus",
            "all": "Wiederholen: Album/Warteschlange",
            "one": "Wiederholen: Aktueller Titel",
        }
        self._set_repeat_icon(mode)
        self.repeat_button.setToolTip(tooltips.get(mode, tooltips["off"]))
        self.repeat_button.setProperty("active", mode != "off")
        self.settings.setValue("player/repeat_mode", mode)
        self.repeat_button.style().unpolish(self.repeat_button)
        self.repeat_button.style().polish(self.repeat_button)

    def _shuffle_changed(self, mode: str) -> None:
        tooltips = {
            "off": "Zufallswiedergabe: Aus",
            "history": "Zufallswiedergabe: Mit Verlauf",
            "fresh": "Zufallswiedergabe: Immer neu auslosen",
        }
        self._set_shuffle_icon(mode)
        self.shuffle_button.setProperty("active", mode != "off")
        self.shuffle_button.setToolTip(tooltips.get(mode, tooltips["off"]))
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
                # Nicht kritisch: Es wird der Platzhalter gezeigt. Trotzdem
                # protokollieren, damit reale Coverfehler eine Spur hinterlassen.
                logger.debug("Cover konnte nicht geladen werden: %s", song.path, exc_info=True)
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
        if self._preview_mode and self.preview_player is not None:
            self.preview_player.seek(self.position_slider.value())
        else:
            self.engine.seek(self.position_slider.value())

    def _volume_changed(self, value: int) -> None:
        self.engine.set_volume(value)
        if self.preview_player is not None:
            self.preview_player.set_volume(value)
        self.settings.setValue("player/volume", value)

    def _show_error(self, message: str) -> None:
        # Transient über die App-Statusleiste melden, ohne den angezeigten
        # Titel dauerhaft zu überschreiben.
        self.status_requested.emit(message, PLAYER_ERROR_TIMEOUT_MS)
        self._set_play_icon(False)
