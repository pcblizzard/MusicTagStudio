from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from musictagstudio.history import HistoryManager  # noqa: E402
from musictagstudio.models.song import Song  # noqa: E402
from musictagstudio.settings import AppSettings  # noqa: E402


def test_disabled_tag_field_is_not_overwritten(tmp_path, monkeypatch):
    from musictagstudio.ui import main_window as mw

    QApplication.instance() or QApplication([])
    win = mw.MainWindow()
    win.history = HistoryManager(tmp_path / "hist")
    monkeypatch.setattr(win, "update_table_row", lambda *a, **k: None)
    monkeypatch.setattr(win, "_preview_changes", lambda items: True)
    # "comment" abgeschaltet -> darf nicht überschrieben werden.
    monkeypatch.setattr(
        mw,
        "load_settings",
        lambda *a, **k: AppSettings(disabled_tag_fields=("comment",)),
    )

    original = Song(path=str(tmp_path / "x.flac"), title="Orig", comment="Behalten")
    win.songs = [original]

    captured: dict = {}

    def fake_save(items):
        captured["items"] = items
        return [(row, song, None) for row, song in items]

    monkeypatch.setattr(mw, "_save_songs_in_parallel", fake_save)

    updated = Song(path=original.path, title="Neu", comment="Geändert")
    win._write_song_updates("desc", [(0, updated)])

    saved_song = captured["items"][0][1]
    assert saved_song.title == "Neu"  # aktiviertes Feld -> geändert
    assert saved_song.comment == "Behalten"  # abgeschaltet -> Originalwert
    win.close()
