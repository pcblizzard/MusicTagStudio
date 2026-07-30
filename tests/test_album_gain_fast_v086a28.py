from __future__ import annotations

from musictagstudio.audio_analysis.analyzer import album_gain_peak_from_results
from musictagstudio.audio_analysis.models import AudioAnalysisResult


def _track(lufs, peak_linear, duration=180.0):
    return AudioAnalysisResult(
        path="x", integrated_lufs=lufs, replaygain_track_peak=peak_linear,
        duration_seconds=duration,
    )


def test_album_peak_is_max_of_track_peaks():
    tracks = [_track(-14.0, 0.9), _track(-12.0, 0.98), _track(-16.0, 0.5)]
    _gain, peak = album_gain_peak_from_results(tracks)
    assert peak == 0.98


def test_album_gain_equal_tracks_matches_single():
    # Alle Tracks gleich laut -> Album-Lautheit = Track-Lautheit -> Gain = -18-(-14).
    tracks = [_track(-14.0, 0.9) for _ in range(3)]
    gain, _peak = album_gain_peak_from_results(tracks)
    assert gain == -18.0 - (-14.0)


def test_album_gain_is_energy_weighted_not_arithmetic():
    # -10 und -20 LUFS gleich lang: energie-gewichtet ~ -12.6 LUFS, nicht -15.
    tracks = [_track(-10.0, 0.5, 60.0), _track(-20.0, 0.5, 60.0)]
    gain, _peak = album_gain_peak_from_results(tracks)
    album_lufs = -18.0 - gain
    assert album_lufs == __import__("pytest").approx(-12.66, abs=0.1)


def test_duration_weighting():
    # Ein sehr langer lauter Track dominiert die Album-Lautheit.
    tracks = [_track(-8.0, 0.5, 600.0), _track(-24.0, 0.5, 10.0)]
    gain, _peak = album_gain_peak_from_results(tracks)
    album_lufs = -18.0 - gain
    assert album_lufs > -9.0  # nahe am lauten Track


def test_empty_or_errored_returns_none():
    assert album_gain_peak_from_results([]) == (None, None)
    err = AudioAnalysisResult(path="x", error="boom", integrated_lufs=-14.0)
    assert album_gain_peak_from_results([err]) == (None, None)
