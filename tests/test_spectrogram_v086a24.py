from __future__ import annotations

from pathlib import Path

import pytest

from musictagstudio.audio_analysis import av_backend, spectrogram


@pytest.fixture
def audio_file(tmp_path: Path) -> Path:
    path = tmp_path / "track.flac"
    path.write_bytes(b"not really audio")
    return path


@pytest.fixture(autouse=True)
def _redirect_cache(monkeypatch, tmp_path: Path) -> None:
    cache_file = tmp_path / "cache" / "audio_analysis.json"
    monkeypatch.setattr(
        spectrogram,
        "default_cache_path",
        lambda: cache_file,
    )


def test_render_calls_pyav_backend(monkeypatch, audio_file: Path):
    captured: dict = {}

    def fake_render(src, dst, *, width, height):
        captured.update(src=src, dst=dst, width=width, height=height)
        Path(dst).write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr(av_backend, "render_spectrogram_png", fake_render)

    output = spectrogram.render_spectrogram(audio_file, width=800, height=400)

    assert output.is_file()
    assert captured["src"] == str(audio_file)
    assert captured["width"] == 800
    assert captured["height"] == 400


def test_cache_hit_skips_render(monkeypatch, audio_file: Path):
    calls = {"count": 0}

    def fake_render(src, dst, *, width, height):
        calls["count"] += 1
        Path(dst).write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr(av_backend, "render_spectrogram_png", fake_render)

    first = spectrogram.render_spectrogram(audio_file)
    second = spectrogram.render_spectrogram(audio_file)

    assert first == second
    assert calls["count"] == 1


def test_backend_failure_raises(monkeypatch, audio_file: Path):
    def fake_render(src, dst, *, width, height):
        raise RuntimeError("boom")

    monkeypatch.setattr(av_backend, "render_spectrogram_png", fake_render)

    with pytest.raises(spectrogram.SpectrogramError):
        spectrogram.render_spectrogram(audio_file)


def test_missing_file_raises():
    with pytest.raises(spectrogram.SpectrogramError):
        spectrogram.render_spectrogram("does-not-exist.flac")
