from __future__ import annotations

import wave
from pathlib import Path

from musictagstudio.audio_analysis.quality import (
    AlbumQuality,
    TrackQuality,
    probe_quality,
    summarize_album,
)


def _make_wav(
    path: Path, *, channels: int = 2, sampwidth: int = 2, framerate: int = 44100
) -> str:
    handle = wave.open(str(path), "wb")
    handle.setnchannels(channels)
    handle.setsampwidth(sampwidth)
    handle.setframerate(framerate)
    handle.writeframes(b"\x00" * sampwidth * channels * 100)
    handle.close()
    return str(path)


def test_probe_reads_wav_technical_values(tmp_path: Path):
    q = probe_quality(_make_wav(tmp_path / "a.wav"))
    assert q.ok
    assert q.codec == "WAV"
    assert q.lossless is True
    assert q.sample_rate == 44100
    assert q.bit_depth == 16
    assert q.channels == 2
    assert q.sample_rate_text == "44.1 kHz"
    assert q.bit_depth_text == "16 Bit"
    assert q.channels_text == "Stereo"


def test_probe_missing_file_reports_error(tmp_path: Path):
    q = probe_quality(tmp_path / "nope.flac")
    assert not q.ok
    assert q.error


def test_probe_non_audio_file_reports_error(tmp_path: Path):
    junk = tmp_path / "note.txt"
    junk.write_text("kein audio", encoding="utf-8")
    q = probe_quality(junk)
    assert not q.ok


def test_lossless_summary_emphasizes_bit_depth():
    q = TrackQuality(
        path="x.flac",
        codec="FLAC",
        sample_rate=44100,
        bit_depth=16,
        channels=2,
        bitrate=900000,
        lossless=True,
    )
    assert q.summary() == "FLAC · 44.1 kHz · 16 Bit · Stereo"


def test_lossy_summary_emphasizes_bitrate_not_bit_depth():
    q = TrackQuality(
        path="x.mp3",
        codec="MP3",
        sample_rate=44100,
        bit_depth=0,
        channels=2,
        bitrate=320000,
        lossless=False,
    )
    assert q.summary() == "MP3 · 44.1 kHz · 320 kbit/s · Stereo"


def test_album_summary_uniform(tmp_path: Path):
    paths = [_make_wav(tmp_path / f"{i}.wav") for i in range(3)]
    album = summarize_album(paths)
    assert album.all_lossless is True
    assert album.is_mixed is False
    assert album.summary() == "WAV · 44.1 kHz · 16 Bit · Stereo"


def test_album_summary_flags_mixed():
    tracks = (
        TrackQuality(path="a", codec="FLAC", sample_rate=44100, bit_depth=16,
                     channels=2, lossless=True),
        TrackQuality(path="b", codec="FLAC", sample_rate=96000, bit_depth=24,
                     channels=2, lossless=True),
    )
    album = AlbumQuality(tracks=tracks)
    assert album.is_mixed is True
    assert "gemischt" in album.summary()


def test_album_all_failed_summary(tmp_path: Path):
    album = summarize_album([str(tmp_path / "missing1.flac")])
    assert album.analyzed == ()
    assert album.summary() == "Keine lesbaren Audiodateien"
