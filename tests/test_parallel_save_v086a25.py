from __future__ import annotations

import threading

from musictagstudio.models.song import Song
from musictagstudio.ui import main_window


def _song(row: int) -> Song:
    return Song(title=f"T{row}", path=f"C:/music/{row}.mp3")


def test_parallel_save_returns_ordered_results(monkeypatch):
    saved: list[str] = []
    lock = threading.Lock()

    def fake_save(path, song):
        with lock:
            saved.append(path)

    monkeypatch.setattr(main_window, "save_song_metadata", fake_save)

    items = [(row, _song(row)) for row in range(5)]
    results = main_window._save_songs_in_parallel(items)

    # Ergebnisreihenfolge entspricht der Eingabereihenfolge.
    assert [row for row, _song, _err in results] == [0, 1, 2, 3, 4]
    assert all(err is None for _row, _song, err in results)
    # Alle Dateien wurden geschrieben (Reihenfolge egal).
    assert sorted(saved) == sorted(item[1].path for item in items)


def test_parallel_save_isolates_failures(monkeypatch):
    def fake_save(path, song):
        if path.endswith("2.mp3"):
            raise OSError("Datei gesperrt")

    monkeypatch.setattr(main_window, "save_song_metadata", fake_save)

    items = [(row, _song(row)) for row in range(4)]
    results = main_window._save_songs_in_parallel(items)

    errors = {row: err for row, _song, err in results if err is not None}
    assert set(errors) == {2}
    assert isinstance(errors[2], OSError)
    # Die übrigen drei gelten als erfolgreich.
    assert sum(1 for _row, _song, err in results if err is None) == 3


def test_parallel_save_empty_is_noop():
    assert main_window._save_songs_in_parallel([]) == []
