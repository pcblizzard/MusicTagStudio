from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("av")

import av  # noqa: E402
import numpy as np  # noqa: E402

from musictagstudio.models.song import Song  # noqa: E402
from musictagstudio.services.metadata_io import (  # noqa: E402
    read_metadata,
    save_song_metadata,
)


def _make(path: Path, codec: str) -> str:
    out = av.open(str(path), "w")
    stream = out.add_stream(codec, rate=44100)
    for _ in range(3):
        arr = (np.random.rand(1, 1024) * 1000).astype("int16")
        frame = av.AudioFrame.from_ndarray(arr, format="s16", layout="mono")
        frame.sample_rate = 44100
        for packet in stream.encode(frame):
            out.mux(packet)
    for packet in stream.encode(None):
        out.mux(packet)
    out.close()
    return str(path)


@pytest.mark.parametrize(
    "name,codec",
    [("a.flac", "flac"), ("a.mp3", "libmp3lame"), ("a.m4a", "aac")],
)
def test_bpm_tag_roundtrip(tmp_path, name, codec):
    path = _make(tmp_path / name, codec)
    save_song_metadata(path, Song(path=path, title="T", artist="A", bpm="128"))
    assert read_metadata(path).bpm == "128"
    # Überschreiben/Leeren funktioniert ebenfalls.
    save_song_metadata(path, Song(path=path, title="T", artist="A", bpm=""))
    assert read_metadata(path).bpm == ""
