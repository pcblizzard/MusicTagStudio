from musictagstudio.audio_analysis.album_check import (
    group_results_by_album,
)
from musictagstudio.audio_analysis.models import (
    AudioAnalysisResult,
)
from musictagstudio.models.song import Song


def test_album_average_metrics():
    songs = [
        Song(
            title="A",
            album="Album",
            album_artist="Artist",
            path="a.flac",
        ),
        Song(
            title="B",
            album="Album",
            album_artist="Artist",
            path="b.flac",
        ),
    ]
    results = {
        "a.flac": AudioAnalysisResult(
            path="a.flac",
            codec="flac",
            sample_rate=44100,
            bit_depth=16,
            channels=2,
            bitrate=800000,
            integrated_lufs=-10.0,
            replaygain_album_gain_db=-7.0,
            replaygain_album_peak=1.1,
            peak_status="normal",
        ),
        "b.flac": AudioAnalysisResult(
            path="b.flac",
            codec="flac",
            sample_rate=44100,
            bit_depth=16,
            channels=2,
            bitrate=1000000,
            integrated_lufs=-12.0,
            replaygain_album_gain_db=-7.0,
            replaygain_album_peak=1.1,
            peak_status="over_zero",
        ),
    }

    summary = group_results_by_album(
        songs,
        results,
    )[0]

    assert summary.average_bitrate == 900000
    assert summary.average_lufs == -11.0
    assert summary.album_gain_db == -7.0
    assert summary.album_peak == 1.1
    assert summary.peak_warning_count == 1
    assert summary.health_score < 100
