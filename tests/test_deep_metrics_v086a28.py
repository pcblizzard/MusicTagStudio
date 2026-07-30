from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

pytest.importorskip("av")
pytest.importorskip("numpy")

from musictagstudio.audio_analysis import deep_metrics  # noqa: E402


def _make_sine(
    path: Path, *, freq: int = 1000, seconds: float = 2.0, amp: float = 0.5,
    sr: int = 44100, channels: int = 2,
) -> str:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        frames = bytearray()
        for n in range(int(sr * seconds)):
            value = int(amp * 32767 * math.sin(2 * math.pi * freq * n / sr))
            frames += struct.pack("<" + "h" * channels, *([value] * channels))
        handle.writeframes(bytes(frames))
    return str(path)


def test_sine_peak_rms_and_crest_factor(tmp_path: Path):
    metrics = deep_metrics.analyze(_make_sine(tmp_path / "s.wav", amp=0.5))
    # 0.5 Vollaussteuerung -> Peak ~ -6 dBFS.
    assert metrics.peak_dbfs == pytest.approx(-6.02, abs=0.2)
    # Reiner Sinus -> Crest-Faktor Peak-RMS ~ 3.01 dB.
    assert metrics.dynamic_range_db == pytest.approx(3.01, abs=0.2)
    assert metrics.clipped_samples == 0
    assert metrics.decoded_format == "s16"


def test_per_channel_metrics_present(tmp_path: Path):
    metrics = deep_metrics.analyze(_make_sine(tmp_path / "st.wav", channels=2))
    assert len(metrics.channels) == 2
    for channel in metrics.channels:
        assert channel.peak_dbfs is not None
        assert channel.dynamic_range_db == pytest.approx(3.01, abs=0.2)


def test_sample_count_matches_duration(tmp_path: Path):
    metrics = deep_metrics.analyze(
        _make_sine(tmp_path / "d.wav", seconds=2.0, sr=44100)
    )
    assert metrics.sample_count == pytest.approx(88200, rel=0.02)


def test_spectral_cutoff_detects_lowpass(tmp_path: Path):
    # Vollband-Rauschen vs. 6-kHz-Sinus: der Sinus schneidet klar tiefer ab.
    tone = deep_metrics.analyze(_make_sine(tmp_path / "t.wav", freq=6000))
    assert tone.spectral_cutoff_hz is not None
    # Der 6-kHz-Ton hat keine Energie in der Nähe von Nyquist (22.05 kHz).
    assert tone.spectral_cutoff_hz < 12000


def test_clipping_counted(tmp_path: Path):
    metrics = deep_metrics.analyze(
        _make_sine(tmp_path / "clip.wav", amp=1.0)
    )
    assert metrics.clipped_samples > 0
