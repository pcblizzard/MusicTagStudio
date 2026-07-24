import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from musictagstudio.lyrics import (
    LyricsDocument,
    LyricsLine,
    LyricsResolution,
)
from musictagstudio.models.song import Song
from musictagstudio.player import PlayerEngine
from musictagstudio.ui.lyrics_dialog import LyricsDialog


class Resolver:
    def local(self, request):
        document = LyricsDocument(
            plain_text="Erste Zeile\n\nZweite Zeile",
            source="LRC-Datei",
        )
        return LyricsResolution(document, (document,))


def app():
    return QApplication.instance() or QApplication([])


def test_dialog_displays_local_lyrics_and_enables_saving(tmp_path, monkeypatch):
    app()
    monkeypatch.setattr(
        "musictagstudio.ui.lyrics_dialog.read_duration_seconds",
        lambda _path: 180.0,
    )
    song = Song(
        title="Titel",
        artist="Künstler",
        album="Album",
        path=str(tmp_path / "Titel.flac"),
    )

    dialog = LyricsDialog(song, resolver=Resolver())

    assert dialog.source_combo.count() == 1
    assert "LRC-Datei" in dialog.source_combo.currentText()
    assert dialog.lyrics_text.toPlainText() == "Erste Zeile\n\nZweite Zeile"
    assert dialog.view_combo.isEnabled() is False
    assert dialog.save_button.isEnabled()
    assert dialog.cached_button.isEnabled()
    dialog.close()


def test_synced_lyrics_can_show_timestamps(tmp_path, monkeypatch):
    app()
    monkeypatch.setattr(
        "musictagstudio.ui.lyrics_dialog.read_duration_seconds",
        lambda _path: 180.0,
    )
    song = Song(
        title="Titel",
        artist="Künstler",
        album="Album",
        path=str(tmp_path / "Titel.flac"),
    )
    document = LyricsDocument(
        plain_text="Hallo",
        synced_lines=(LyricsLine(1250, "Hallo"),),
        source="LRCLIB",
        fetched_at="2026-07-20T10:30:00+00:00",
    )

    class SyncedResolver:
        def local(self, request):
            return LyricsResolution(document, (document,))

    dialog = LyricsDialog(song, resolver=SyncedResolver())
    dialog.timestamps_checkbox.setChecked(True)

    assert dialog.lyrics_text.toPlainText() == "[00:01.25] Hallo"
    assert "LRCLIB · lokal zwischengespeichert" in dialog.source_combo.currentText()
    assert "20.07.2026" in dialog.source_details.text()
    dialog.close()


def test_karaoke_mode_follows_player_position(tmp_path, monkeypatch):
    app()
    QSettings("MusicTagStudio", "MusicTagStudio").setValue(
        "lyrics/view_mode", "text"
    )
    monkeypatch.setattr(
        "musictagstudio.ui.lyrics_dialog.read_duration_seconds",
        lambda _path: 180.0,
    )
    song = Song(
        title="Titel",
        artist="Künstler",
        album="Album",
        path=str(tmp_path / "Titel.flac"),
    )
    document = LyricsDocument(
        plain_text="Eins\nZwei\nDrei",
        synced_lines=(
            LyricsLine(0, "Eins"),
            LyricsLine(1000, "Zwei"),
            LyricsLine(2000, "Drei"),
        ),
        source="LRCLIB",
    )

    class SyncedResolver:
        def local(self, request):
            return LyricsResolution(document, (document,))

    engine = PlayerEngine()
    engine.queue.replace([song], 0)
    dialog = LyricsDialog(
        song,
        resolver=SyncedResolver(),
        player_engine=engine,
    )
    dialog.view_combo.setCurrentIndex(1)
    engine.position_changed.emit(1500)

    assert dialog._karaoke_line == 1
    assert dialog.lyrics_text.extraSelections()
    assert dialog.timestamps_checkbox.isEnabled() is False
    dialog.close()
    engine.deleteLater()


def test_not_found_and_offline_states_are_distinct(tmp_path):
    app()
    dialog = LyricsDialog(
        Song(path=str(tmp_path / "missing.flac")),
        resolver=Resolver(),
    )

    dialog._online_failed("Keine Lyrics bei LRCLIB gefunden.")
    assert dialog.status_label.property("statusKind") == "not_found"
    dialog._online_failed("LRCLIB ist nicht erreichbar: offline")
    assert dialog.status_label.property("statusKind") == "offline"
    dialog.close()


def test_dialog_shows_live_warning(tmp_path):
    app()
    song = Song(
        title="Titel (Live)",
        artist="Künstler",
        album="Live in Berlin",
        path=str(tmp_path / "Titel.flac"),
    )
    document = LyricsDocument(
        plain_text="Studiotext",
        source="LRCLIB",
        metadata={"ti": "Titel", "al": "Studioalbum"},
    )

    class LiveResolver:
        def local(self, request):
            return LyricsResolution(
                document,
                (document,),
                "Hinweis: Dies ist eine Live-Version.",
            )

    dialog = LyricsDialog(song, resolver=LiveResolver())

    assert dialog.warning_label.isVisibleTo(dialog)
    assert "Live-Version" in dialog.warning_label.text()
    dialog.close()


def test_lrclib_actions_are_disabled_without_readable_duration(tmp_path):
    app()
    song = Song(
        title="Titel",
        artist="Künstler",
        album="Album",
        path=str(tmp_path / "missing.flac"),
    )

    dialog = LyricsDialog(song, resolver=Resolver())

    assert not dialog.cached_button.isEnabled()
    assert not dialog.live_button.isEnabled()
    assert "Titeldauer" in dialog.status_label.text()
    assert dialog.save_button.isEnabled()
    dialog.close()
