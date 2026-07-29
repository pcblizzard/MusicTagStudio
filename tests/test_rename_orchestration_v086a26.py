from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from musictagstudio.history import HistoryManager  # noqa: E402
from musictagstudio.models.song import Song  # noqa: E402
from musictagstudio.settings import AppSettings  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):
    from musictagstudio.ui import main_window as mw

    QApplication.instance() or QApplication([])
    win = mw.MainWindow()
    # History in ein Temp-Verzeichnis umhängen (kein echtes Projekt-Root).
    win.history = HistoryManager(tmp_path / "hist")
    # Neu-Einlesen vom Datenträger im Test überspringen.
    monkeypatch.setattr(win, "scan_music", lambda: None)
    # Premium-Gating für die Umbenennungs-Tests freischalten.
    monkeypatch.setattr(mw, "is_feature_enabled", lambda *a, **k: True)
    # Nicht die echte config.toml lesen (Namensschema/Key des Entwicklers) –
    # deterministische Standardeinstellungen erzwingen.
    monkeypatch.setattr(mw, "load_settings", lambda *a, **k: AppSettings())
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


def test_rename_free_tier_allows_then_blocks(tmp_path, monkeypatch):
    # Eigenes Fenster OHNE die Freischalt-Fixture -> Gratis-Stufe greift.
    from musictagstudio.ui import main_window as mw
    from musictagstudio import usage_limits

    monkeypatch.setattr(mw, "ChangePreviewDialog", _AcceptDialog)
    monkeypatch.setattr(mw, "load_settings", lambda *a, **k: AppSettings())
    QApplication.instance() or QApplication([])
    win = mw.MainWindow()
    monkeypatch.setattr(win, "scan_music", lambda: None)
    win.history = HistoryManager(tmp_path / "hist")
    win.folder = str(tmp_path)

    # Gratis-Kontingent: Umbenennung ist ohne Lizenz erlaubt.
    a = _make_file(tmp_path / "raw1.flac")
    win.songs = [Song(path=a, track="1", title="Erster")]
    win.rename_files()
    assert (tmp_path / "01 - Erster.flac").is_file()
    assert usage_limits.remaining_free_renames() == usage_limits.FREE_RENAME_LIMIT - 1

    # Kontingent erschöpfen -> jetzt wird geblockt.
    usage_limits.record_renames(usage_limits.FREE_RENAME_LIMIT)
    captured: list[str] = []

    class _RejectPremium:
        DialogCode = QDialog.DialogCode

        def __init__(self, *args, **kwargs):
            captured.append("premium-hint")

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(mw, "PremiumDialog", _RejectPremium)
    b = _make_file(tmp_path / "raw2.flac")
    win.songs = [Song(path=b, track="2", title="Zweiter")]
    win.rename_files()
    assert Path(b).is_file()  # nicht umbenannt
    assert not (tmp_path / "02 - Zweiter.flac").exists()
    assert captured  # Premium-/Limit-Hinweis wurde angezeigt
    win.close()


def test_rename_releases_playing_file(window, tmp_path, monkeypatch):
    win, mw = window
    monkeypatch.setattr(mw, "ChangePreviewDialog", _AcceptDialog)

    a = _make_file(tmp_path / "raw1.flac")
    win.folder = str(tmp_path)
    song = Song(path=a, track="1", title="Spielt")
    win.songs = [song]
    # Nur das Queue-Modell setzen (current_song liefert die Datei), ohne sie
    # ins QMediaPlayer-Backend zu laden – das würde offscreen blockieren.
    win.player_bar.engine.queue.replace([song], 0)

    released: list[bool] = []
    monkeypatch.setattr(
        win.player_bar.engine, "release_file", lambda: released.append(True)
    )

    win.rename_files()

    # Freigabe wurde ausgelöst und die Datei umbenannt.
    assert released
    assert (tmp_path / "01 - Spielt.flac").is_file()


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
