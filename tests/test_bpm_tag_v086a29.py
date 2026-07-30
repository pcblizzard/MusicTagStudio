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
    stereo = codec == "wmav2"  # wmav2 verlangt Stereo
    layout = "stereo" if stereo else "mono"
    cols = 1024 * 2 if stereo else 1024  # packed s16: interleaved
    out = av.open(str(path), "w")
    stream = out.add_stream(codec, rate=44100)
    if stereo:
        stream.bit_rate = 128000  # wmav2 braucht eine gesetzte Bitrate
    for _ in range(3):
        arr = (np.random.rand(1, cols) * 1000).astype("int16")
        frame = av.AudioFrame.from_ndarray(arr, format="s16", layout=layout)
        frame.sample_rate = 44100
        for packet in stream.encode(frame):
            out.mux(packet)
    for packet in stream.encode(None):
        out.mux(packet)
    out.close()
    return str(path)


@pytest.mark.parametrize(
    "name,codec",
    [
        ("a.flac", "flac"),
        ("a.mp3", "libmp3lame"),
        ("a.m4a", "aac"),
        # WavPack teilt den APEv2-Reader/Writer mit Monkey's Audio (.ape).
        ("a.wv", "wavpack"),
        ("a.wma", "wmav2"),
    ],
)
def test_bpm_tag_roundtrip(tmp_path, name, codec):
    path = _make(tmp_path / name, codec)
    save_song_metadata(path, Song(path=path, title="T", artist="A", bpm="128"))
    assert read_metadata(path).bpm == "128"
    # Überschreiben/Leeren funktioniert ebenfalls.
    save_song_metadata(path, Song(path=path, title="T", artist="A", bpm=""))
    assert read_metadata(path).bpm == ""
