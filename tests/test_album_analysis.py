from musictagstudio.audio_analysis.album_check import (
    group_results_by_album,
)
from musictagstudio.audio_analysis.models import (
    AudioAnalysisResult,
)
from musictagstudio.models.song import Song


def test_album_outlier_detection():
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
        Song(
            title="C",
            album="Album",
            album_artist="Artist",
            path="c.flac",
        ),
    ]
    results = {
        "a.flac": AudioAnalysisResult(
            path="a.flac",
            codec="flac",
            sample_rate=44100,
            bit_depth=16,
            channels=2,
        ),
        "b.flac": AudioAnalysisResult(
            path="b.flac",
            codec="flac",
            sample_rate=44100,
            bit_depth=16,
            channels=2,
        ),
        "c.flac": AudioAnalysisResult(
            path="c.flac",
            codec="flac",
            sample_rate=48000,
            bit_depth=24,
            channels=2,
        ),
    }

    summaries = group_results_by_album(
        songs,
        results,
    )

    assert len(summaries) == 1
    assert summaries[0].track_count == 3
    assert summaries[0].technical_outliers == (
        "c.flac",
    )
