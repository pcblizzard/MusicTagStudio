from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from musictagstudio.audio_analysis import spectrogram
from musictagstudio.audio_analysis.models import FFmpegInstallation


def _installation() -> FFmpegInstallation:
    return FFmpegInstallation(
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        version="test",
    )


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


def test_render_builds_showspectrumpic_command(monkeypatch, audio_file: Path):
    captured: dict[str, list[str]] = {}

    def fake_run(command, **_kwargs):
        captured["command"] = command
        Path(command[-1]).write_bytes(b"PNGDATA")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(spectrogram.subprocess, "run", fake_run)

    output = spectrogram.render_spectrogram(audio_file, _installation())

    assert output.is_file()
    command = captured["command"]
    filter_arg = command[command.index("-lavfi") + 1]
    assert filter_arg.startswith("showspectrumpic=")
    assert "legend=1" in filter_arg
    assert str(audio_file) in command


def test_cache_hit_skips_ffmpeg(monkeypatch, audio_file: Path):
    calls = {"count": 0}

    def fake_run(command, **_kwargs):
        calls["count"] += 1
        Path(command[-1]).write_bytes(b"PNGDATA")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(spectrogram.subprocess, "run", fake_run)

    first = spectrogram.render_spectrogram(audio_file, _installation())
    second = spectrogram.render_spectrogram(audio_file, _installation())

    assert first == second
    assert calls["count"] == 1


def test_ffmpeg_failure_raises(monkeypatch, audio_file: Path):
    def fake_run(command, **_kwargs):
        return subprocess.CompletedProcess(command, 1, "", "boom")

    monkeypatch.setattr(spectrogram.subprocess, "run", fake_run)

    with pytest.raises(spectrogram.SpectrogramError):
        spectrogram.render_spectrogram(audio_file, _installation())


def test_missing_file_raises():
    with pytest.raises(spectrogram.SpectrogramError):
        spectrogram.render_spectrogram(
            "does-not-exist.flac",
            _installation(),
        )


def test_unavailable_ffmpeg_raises(audio_file: Path):
    with pytest.raises(spectrogram.SpectrogramError):
        spectrogram.render_spectrogram(
            audio_file,
            FFmpegInstallation(ffmpeg_path="", ffprobe_path=""),
        )
