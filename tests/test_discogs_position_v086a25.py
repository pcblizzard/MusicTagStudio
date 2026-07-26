from __future__ import annotations

from musictagstudio.media_library.presentation import discogs_position


def test_cd_multidisc_positions():
    assert discogs_position("1-2", 5) == (1, 2)
    assert discogs_position("2.05", 5) == (2, 5)


def test_plain_track_number():
    assert discogs_position("7", 99) == (1, 7)


def test_vinyl_sides_use_sequential_fallback_no_collision():
    # A-Seite und B-Seite duerfen nicht beide bei Track 1 beginnen.
    positions = ["A1", "A2", "A3", "B1", "B2", "B3"]
    numbers = [
        discogs_position(pos, index)
        for index, pos in enumerate(positions, start=1)
    ]
    assert numbers == [(1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6)]


def test_empty_position_uses_fallback():
    assert discogs_position("", 4) == (1, 4)
