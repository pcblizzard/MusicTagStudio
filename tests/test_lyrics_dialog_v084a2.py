import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from musictagstudio.lyrics import (
    LyricsDocument,
    LyricsResolution,
)
from musictagstudio.models.song import Song
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
    assert dialog.save_button.isEnabled()
    assert dialog.cached_button.isEnabled()
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
