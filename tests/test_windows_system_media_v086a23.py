import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from musictagstudio.models.song import Song
from musictagstudio.player import PlayerEngine
from musictagstudio.player.windows_smtc import (
    WindowsSystemMediaBridge,
    system_media_metadata,
)


def test_system_media_metadata_uses_safe_fallbacks():
    song = Song(
        title="Titel",
        artist="",
        album_artist="Albumkünstler",
        album="Album",
        path="C:/Music/file.flac",
    )

    assert system_media_metadata(song) == {
        "title": "Titel",
        "artist": "Albumkünstler",
        "album": "Album",
        "album_artist": "Albumkünstler",
    }
    assert system_media_metadata(Song(path="C:/Music/file.flac"))["title"] == "file"


def test_system_media_buttons_are_forwarded_to_engine():
    QApplication.instance() or QApplication([])
    engine = PlayerEngine()
    calls = []
    engine.toggle = lambda: calls.append("toggle")
    engine.next = lambda: calls.append("next")
    engine.previous = lambda: calls.append("previous")
    engine.stop = lambda: calls.append("stop")
    bridge = WindowsSystemMediaBridge(engine)
    buttons = SimpleNamespace(
        PLAY=0,
        PAUSE=1,
        STOP=2,
        NEXT=6,
        PREVIOUS=7,
    )
    bridge._media = SimpleNamespace(
        SystemMediaTransportControlsButton=buttons
    )

    for button in (buttons.PLAY, buttons.NEXT, buttons.PREVIOUS, buttons.STOP):
        bridge._button_pressed(None, SimpleNamespace(button=button))

    assert calls == ["toggle", "next", "previous", "stop"]
    engine.deleteLater()


def test_cover_reference_uses_cached_embedded_cover(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    engine = PlayerEngine()
    bridge = WindowsSystemMediaBridge(engine)
    captured = {}

    class Reference:
        @staticmethod
        def create_from_uri(uri):
            captured["uri"] = uri
            return "reference"

    bridge._foundation = SimpleNamespace(Uri=lambda value: value)
    bridge._streams = SimpleNamespace(RandomAccessStreamReference=Reference)
    monkeypatch.setattr(
        "musictagstudio.player.windows_smtc.QStandardPaths.writableLocation",
        lambda _location: str(tmp_path),
    )
    song = Song(
        title="Titel",
        cover=b"\x89PNG\r\n\x1a\ncover-data",
    )

    assert bridge._cover_reference(song) == "reference"
    assert captured["uri"].endswith(".png")
    assert list((tmp_path / "system-media").glob("*.png"))
    engine.deleteLater()
