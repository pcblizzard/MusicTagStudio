from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

pytest.importorskip("av")

import av  # noqa: E402

from musictagstudio.services.convert import (  # noqa: E402
    FORMATS,
    ConversionError,
    convert_file,
    target_path,
)


def _tone(path: Path, *, sr=44100, seconds=1.0) -> str:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        frames = bytearray()
        for n in range(int(sr * seconds)):
            value = int(0.3 * 32767 * math.sin(2 * math.pi * 440 * n / sr))
            frames += struct.pack("<hh", value, value)
        handle.writeframes(bytes(frames))
    return str(path)


def _codec(path) -> str:
    with av.open(str(path)) as container:
        return container.streams.audio[0].codec_context.name


def test_target_path_uses_extension(tmp_path):
    out = target_path("/x/song.flac", tmp_path, FORMATS["mp3"])
    assert out.name == "song.mp3" and out.parent == tmp_path


@pytest.mark.parametrize("key", ["mp3", "aac", "flac", "alac"])
def test_convert_keeps_sample_rate(tmp_path, key):
    src = _tone(tmp_path / "s.wav")
    fmt = FORMATS[key]
    dst = target_path(src, tmp_path, fmt)
    convert_file(src, dst, fmt, bitrate=192000)
    assert dst.is_file() and dst.stat().st_size > 0
    with av.open(str(dst)) as c:
        assert c.streams.audio[0].codec_context.sample_rate == 44100


def test_opus_forced_to_48k(tmp_path):
    src = _tone(tmp_path / "s.wav")
    fmt = FORMATS["opus"]
    dst = target_path(src, tmp_path, fmt)
    convert_file(src, dst, fmt)
    with av.open(str(dst)) as c:
        assert c.streams.audio[0].codec_context.sample_rate == 48000


def test_missing_source_raises(tmp_path):
    with pytest.raises(ConversionError):
        convert_file(tmp_path / "nope.flac", tmp_path / "o.mp3", FORMATS["mp3"])
