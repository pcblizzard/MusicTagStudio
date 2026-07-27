from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from musictagstudio.history import HistoryManager  # noqa: E402
from musictagstudio.models.song import Song  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):
    from musictagstudio.ui import main_window as mw

    QApplication.instance() or QApplication([])
    win = mw.MainWindow()
    # History in ein Temp-Verzeichnis umhängen (kein echtes Projekt-Root).
    win.history = HistoryManager(tmp_path / "hist")
    # Neu-Einlesen vom Datenträger im Test überspringen.
    monkeypatch.setattr(win, "scan_music", lambda: None)
    yield win, mw
    win.close()


class _AcceptDialog:
    """Stub für ChangePreviewDialog, der immer 'Save' zurückgibt."""

    class DialogCode:
        Accepted = 1

    def __init__(self, *args, **kwargs):
        pass

    def exec(self):
        return self.DialogCode.Accepted


def _make_file(path: Path, data: bytes = b"audio") -> str:
    path.write_bytes(data)
    return str(path)


def test_rename_files_renames_and_records_history(window, tmp_path, monkeypatch):
    win, mw = window
    monkeypatch.setattr(mw, "ChangePreviewDialog", _AcceptDialog)

    a = _make_file(tmp_path / "raw1.flac")
    b = _make_file(tmp_path / "raw2.flac")
    win.folder = str(tmp_path)
    win.songs = [
        Song(path=a, track="1", title="Erster"),
        Song(path=b, track="2", title="Zweiter"),
    ]

    win.rename_files()

    assert (tmp_path / "01 - Erster.flac").is_file()
    assert (tmp_path / "02 - Zweiter.flac").is_file()
    assert not Path(a).exists() and not Path(b).exists()
    assert win.history.can_undo

    # Undo benennt zurück.
    win.history.undo()
    assert Path(a).is_file() and Path(b).is_file()


def test_rename_files_skips_collision(window, tmp_path, monkeypatch):
    win, mw = window
    monkeypatch.setattr(mw, "ChangePreviewDialog", _AcceptDialog)

    a = _make_file(tmp_path / "raw1.flac")
    b = _make_file(tmp_path / "raw2.flac")
    win.folder = str(tmp_path)
    # Beide erzeugen denselben Zielnamen -> zweiter kollidiert.
    win.songs = [
        Song(path=a, track="1", title="Gleich"),
        Song(path=b, track="1", title="Gleich"),
    ]

    win.rename_files()

    assert (tmp_path / "01 - Gleich.flac").is_file()
    # Nur eine Datei wurde umbenannt; die kollidierende blieb erhalten.
    assert Path(b).is_file()
    assert win.history.can_undo
