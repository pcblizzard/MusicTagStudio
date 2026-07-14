from pathlib import Path

from musictagstudio.audio_analysis.cache import (
    AudioAnalysisCache,
)
from musictagstudio.audio_analysis.models import (
    AudioAnalysisResult,
)


def test_analysis_cache_roundtrip(
    tmp_path: Path,
):
    audio_file = tmp_path / "song.flac"
    audio_file.write_bytes(b"audio")

    cache = AudioAnalysisCache(
        tmp_path / "cache.json"
    )
    result = AudioAnalysisResult(
        path=str(audio_file),
        codec="flac",
        sample_rate=44100,
        integrated_lufs=-11.5,
        peak_status="over_zero",
    )

    cache.put(result)
    cached = cache.get(audio_file)

    assert cached is not None
    assert cached.codec == "flac"
    assert cached.integrated_lufs == -11.5
    assert cached.from_cache


def test_changed_file_invalidates_cache(
    tmp_path: Path,
):
    audio_file = tmp_path / "song.flac"
    audio_file.write_bytes(b"audio")

    cache = AudioAnalysisCache(
        tmp_path / "cache.json"
    )
    cache.put(
        AudioAnalysisResult(
            path=str(audio_file),
            codec="flac",
        )
    )

    audio_file.write_bytes(
        b"changed audio"
    )

    assert cache.get(audio_file) is None
