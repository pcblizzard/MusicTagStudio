from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("av")

from musictagstudio.audio_analysis.bpm import detect_bpm  # noqa: E402


def _click_track(path: Path, bpm: int, *, beats: int = 40, sr: int = 44100) -> str:
    beat_len = int(sr * 60 / bpm)
    one = np.zeros(beat_len, dtype=np.int16)
    click = (0.8 * 32767 * np.sin(
        2 * np.pi * 1000 * np.arange(int(sr * 0.01)) / sr
    )).astype(np.int16)
    one[: click.size] = click
    signal = np.tile(one, beats)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(signal.tobytes())
    return str(path)


@pytest.mark.parametrize("bpm", [90, 120, 140])
def test_detect_bpm_close_to_truth(tmp_path, bpm):
    detected = detect_bpm(_click_track(tmp_path / f"{bpm}.wav", bpm))
    assert detected is not None
    assert abs(detected - bpm) <= 2.0


def test_detect_bpm_missing_file_returns_none(tmp_path):
    assert detect_bpm(str(tmp_path / "nope.wav")) is None
