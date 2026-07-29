from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

pytest.importorskip("av")

from musictagstudio.audio_analysis import av_backend  # noqa: E402


def _make_tone(path: Path, *, seconds: float = 3.0, amp: float = 0.25) -> str:
    sr = 44100
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        frames = bytearray()
        for n in range(int(sr * seconds)):
            value = int(amp * 32767 * math.sin(2 * math.pi * 1000 * n / sr))
            frames += struct.pack("<hh", value, value)
        handle.writeframes(bytes(frames))
    return str(path)


def test_probe_reads_wav(tmp_path: Path):
    info = av_backend.probe(_make_tone(tmp_path / "a.wav"))
    assert info["sample_rate"] == 44100
    assert info["channels"] == 2
    assert info["bit_depth"] == 16
    assert info["duration_seconds"] == pytest.approx(3.0, abs=0.2)


def test_loudness_matches_signal_level(tmp_path: Path):
    # -12 dBFS Sinus -> integrierte Lautheit nahe -12 LUFS.
    data = av_backend.measure_loudness_json([_make_tone(tmp_path / "b.wav")])
    assert data.get("input_i") is not None
    assert float(data["input_i"]) == pytest.approx(-12.0, abs=1.5)
    assert data.get("input_tp") is not None


def test_album_loudness_over_multiple_files(tmp_path: Path):
    paths = [_make_tone(tmp_path / f"{i}.wav") for i in range(2)]
    data = av_backend.measure_loudness_json(paths)
    assert float(data["input_i"]) == pytest.approx(-12.0, abs=1.5)


def test_loudness_empty_for_missing_files(tmp_path: Path):
    assert av_backend.measure_loudness_json([str(tmp_path / "nope.wav")]) == {}


def test_render_spectrogram_writes_png(tmp_path: Path):
    tone = _make_tone(tmp_path / "c.wav")
    out = tmp_path / "spec.png"
    av_backend.render_spectrogram_png(tone, str(out), width=320, height=200)
    assert out.is_file()
    assert out.stat().st_size > 0
    # PNG-Signatur
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
