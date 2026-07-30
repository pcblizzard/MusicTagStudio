from __future__ import annotations

from musictagstudio.models.song import Song
from musictagstudio.services.song_filter import distinct_values, matches


def _song(**kw):
    return Song(**kw)


def test_text_matches_any_field():
    s = _song(title="Freier Fall", artist="Clueso", album="Album", genre="Pop")
    assert matches(s, text="fall")
    assert matches(s, text="clue")
    assert not matches(s, text="rock")


def test_genre_filter_exact_casefold():
    assert matches(_song(genre="Rock"), genre="rock")
    assert not matches(_song(genre="Pop"), genre="Rock")


def test_artist_filter_checks_album_artist_too():
    s = _song(artist="Feature Guy", album_artist="Main Artist")
    assert matches(s, artist="main artist")
    assert matches(s, artist="Feature Guy")
    assert not matches(s, artist="Someone Else")


def test_combined_criteria_all_must_match():
    s = _song(title="Song", artist="A", genre="Rock")
    assert matches(s, text="song", genre="Rock", artist="A")
    assert not matches(s, text="song", genre="Pop", artist="A")


def test_empty_criteria_match_all():
    assert matches(_song(title="X"))


def test_bpm_filter_within_tolerance():
    assert matches(_song(bpm="120"), bpm="120")
    assert matches(_song(bpm="122"), bpm="120", bpm_tolerance=3)
    assert not matches(_song(bpm="130"), bpm="120", bpm_tolerance=3)
    # ohne BPM-Tag fällt der Titel bei gesetztem BPM-Filter raus
    assert not matches(_song(bpm=""), bpm="120")


def test_distinct_values_sorted_unique():
    songs = [_song(genre="Rock"), _song(genre="pop"), _song(genre="Rock"),
             _song(genre="")]
    assert distinct_values(songs, "genre") == ["pop", "Rock"]


def test_distinct_artist_includes_album_artist():
    songs = [_song(artist="B", album_artist="A"), _song(artist="C")]
    assert distinct_values(songs, "artist") == ["A", "B", "C"]


# --- library_stats -----------------------------------------------------------

import math  # noqa: E402
import struct  # noqa: E402
import wave  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from musictagstudio.services.library_stats import compute_stats  # noqa: E402


def _wav(path: Path, *, sr=44100) -> str:
    with wave.open(str(path), "wb") as h:
        h.setnchannels(2)
        h.setsampwidth(2)
        h.setframerate(sr)
        frames = bytearray()
        for n in range(sr):
            v = int(0.2 * 32767 * math.sin(2 * math.pi * 440 * n / sr))
            frames += struct.pack("<hh", v, v)
        h.writeframes(bytes(frames))
    return str(path)


def test_compute_stats_counts_lossless_wav(tmp_path):
    a = _wav(tmp_path / "a.wav")
    b = _wav(tmp_path / "b.wav", sr=48000)
    stats = compute_stats([a, b, str(tmp_path / "missing.wav")])
    assert stats.total == 3
    assert stats.readable == 2
    assert stats.lossless == 2 and stats.lossy == 0
    assert stats.lossless_percent == pytest.approx(100.0)
    assert 44100 in stats.by_sample_rate and 48000 in stats.by_sample_rate


def test_compute_stats_empty():
    stats = compute_stats([])
    assert stats.total == 0 and stats.readable == 0
