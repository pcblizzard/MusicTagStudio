from __future__ import annotations

from musictagstudio.audio_analysis.dedupe import (
    DuplicateTrack,
    find_duplicate_groups,
    normalize,
    rank_for_keeping,
)
from musictagstudio.audio_analysis.quality import TrackQuality


def _track(path, artist, title, *, lossless=False, bit=0, rate=44100,
           bitrate=0, duration=200.0):
    q = TrackQuality(
        path=path, codec="x", sample_rate=rate, bit_depth=bit,
        channels=2, bitrate=bitrate, lossless=lossless,
    )
    return DuplicateTrack(
        path=path, artist=artist, title=title, album="A",
        duration=duration, quality=q,
    )


def test_normalize_strips_brackets_feat_and_punctuation():
    assert normalize("Song (Remastered 2011)") == "song"
    assert normalize("Hey! feat. Someone") == "hey"
    assert normalize("  A  B ") == "a b"


def test_flac_kept_over_mp3():
    flac = _track("a.flac", "X", "Song", lossless=True, bit=16, bitrate=900000)
    mp3 = _track("a.mp3", "X", "Song", lossless=False, bitrate=320000)
    groups = find_duplicate_groups([mp3, flac])
    assert len(groups) == 1
    assert groups[0].keep.path == "a.flac"
    assert [t.path for t in groups[0].removable] == ["a.mp3"]


def test_higher_bit_depth_and_rate_wins():
    hi = _track("hi.flac", "X", "S", lossless=True, bit=24, rate=96000)
    lo = _track("lo.flac", "X", "S", lossless=True, bit=16, rate=44100)
    ranked = rank_for_keeping([lo, hi])
    assert ranked[0].path == "hi.flac"


def test_higher_bitrate_wins_among_lossy():
    a = _track("a.mp3", "X", "S", bitrate=128000)
    b = _track("b.mp3", "X", "S", bitrate=320000)
    ranked = rank_for_keeping([a, b])
    assert ranked[0].path == "b.mp3"


def test_no_group_for_single_track():
    assert find_duplicate_groups([_track("a.flac", "X", "Solo")]) == []


def test_different_durations_are_separate_recordings():
    studio = _track("studio.flac", "X", "S", lossless=True, duration=200.0)
    live = _track("live.flac", "X", "S", lossless=True, duration=320.0)
    assert find_duplicate_groups([studio, live]) == []


def test_same_song_close_duration_groups():
    a = _track("a.flac", "X", "S", lossless=True, duration=200.0)
    b = _track("b.mp3", "X", "S", duration=201.5)
    groups = find_duplicate_groups([a, b])
    assert len(groups) == 1 and groups[0].size == 2


def test_tracks_without_artist_and_title_ignored():
    assert find_duplicate_groups([_track("a.flac", "", ""), _track("b.flac", "", "")]) == []


def test_deterministic_tiebreak_by_path():
    a = _track("z.flac", "X", "S", lossless=True, bit=16, rate=44100)
    b = _track("a.flac", "X", "S", lossless=True, bit=16, rate=44100)
    ranked = rank_for_keeping([a, b])
    assert ranked[0].path == "a.flac"  # bei Gleichstand Pfad-alphabetisch
