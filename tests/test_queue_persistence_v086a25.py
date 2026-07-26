from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json

from PySide6.QtWidgets import QApplication

from musictagstudio.models.song import Song
from musictagstudio.player.model import song_from_dict, song_to_dict


class FakeSettings:
    """In-Memory-Ersatz für QSettings (nur die genutzten Methoden)."""

    def __init__(self, *_args):
        self.store: dict[str, object] = {}

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):
        self.store[key] = value

    def remove(self, key):
        self.store.pop(key, None)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _song(path: str, title: str) -> Song:
    return Song(
        title=title,
        artist="Danger Dan",
        album="Album",
        track="1",
        disc="1",
        path=path,
        cover=b"BINARY-COVER-BYTES",
    )


def test_song_dict_roundtrip_drops_cover():
    song = _song("C:/m/01.flac", "Lauf davon")
    data = song_to_dict(song)

    assert "cover" not in data
    assert data["title"] == "Lauf davon"
    assert data["path"] == "C:/m/01.flac"

    restored = song_from_dict(data)
    assert restored.title == "Lauf davon"
    assert restored.path == "C:/m/01.flac"
    assert restored.cover is None


def test_song_from_dict_ignores_unknown_and_missing_keys():
    restored = song_from_dict({"title": "X", "unbekannt": "y"})
    assert restored.title == "X"
    assert restored.artist == ""


def _make_bar(monkeypatch):
    monkeypatch.setattr(
        "musictagstudio.player.widget.QSettings", FakeSettings
    )
    from musictagstudio.player.widget import PlayerBar

    _app()
    return PlayerBar()


def test_save_and_restore_queue_roundtrip(monkeypatch, tmp_path):
    file_one = tmp_path / "01.mp3"
    file_two = tmp_path / "02.mp3"
    file_one.write_bytes(b"")
    file_two.write_bytes(b"")

    bar = _make_bar(monkeypatch)
    bar.engine.set_queue(
        [_song(str(file_one), "Eins"), _song(str(file_two), "Zwei")],
        1,
        autoplay=False,
    )
    bar.save_queue()

    # Es liegt genau ein serialisierter Eintrag mit beiden Titeln vor.
    payload = json.loads(bar.settings.value("player/queue"))
    assert [entry["title"] for entry in payload["songs"]] == ["Eins", "Zwei"]
    assert payload["current_index"] == 1

    # Neue Leiste mit denselben Settings stellt die Queue wieder her.
    from musictagstudio.player.widget import PlayerBar

    restored_bar = PlayerBar()
    restored_bar.settings = bar.settings
    restored_bar.restore_queue()

    titles = [song.title for song in restored_bar.engine.queue.songs]
    assert titles == ["Eins", "Zwei"]
    assert restored_bar.engine.queue.current_index == 1
    bar.deleteLater()
    restored_bar.deleteLater()


def test_restore_skips_missing_files(monkeypatch, tmp_path):
    present = tmp_path / "present.mp3"
    present.write_bytes(b"")

    bar = _make_bar(monkeypatch)
    payload = {
        "songs": [
            song_to_dict(_song(str(tmp_path / "weg.mp3"), "Fehlt")),
            song_to_dict(_song(str(present), "Da")),
        ],
        "current_index": 0,
    }
    bar.settings.setValue("player/queue", json.dumps(payload))
    bar.restore_queue()

    titles = [song.title for song in bar.engine.queue.songs]
    assert titles == ["Da"]
    # Der gespeicherte Index zeigte auf die fehlende Datei -> auf 0 geklemmt.
    assert bar.engine.queue.current_index == 0
    bar.deleteLater()


def test_save_empty_queue_removes_key(monkeypatch):
    bar = _make_bar(monkeypatch)
    bar.settings.setValue("player/queue", "irgendwas")
    bar.save_queue()
    assert bar.settings.value("player/queue") is None
    bar.deleteLater()


def test_restore_without_saved_queue_is_noop(monkeypatch):
    bar = _make_bar(monkeypatch)
    # Frische Settings: kein player/queue -> Queue bleibt leer.
    bar.restore_queue()
    assert bar.engine.queue.songs == []
    bar.deleteLater()
