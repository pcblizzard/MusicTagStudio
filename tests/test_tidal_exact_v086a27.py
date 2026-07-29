from __future__ import annotations

from musictagstudio.providers.tidal_exact import (
    ExactQuality,
    album_exact_quality,
    extract_stream_quality,
)


class _FakeStream:
    def __init__(self, bit_depth=0, sample_rate=0, audio_quality=""):
        self.bit_depth = bit_depth
        self.sample_rate = sample_rate
        self.audio_quality = audio_quality


class _FakeTrack:
    def __init__(self, stream, audio_quality=""):
        self._stream = stream
        self.audio_quality = audio_quality

    def get_stream(self):
        if isinstance(self._stream, Exception):
            raise self._stream
        return self._stream


class _FakeAlbum:
    def __init__(self, tracks):
        self._tracks = tracks

    def tracks(self):
        return self._tracks


class _FakeSession:
    def __init__(self, album):
        self._album = album

    def album(self, album_id):
        if isinstance(self._album, Exception):
            raise self._album
        return self._album


def test_extract_reads_bit_depth_and_sample_rate():
    q = extract_stream_quality(
        _FakeStream(bit_depth=24, sample_rate=48000, audio_quality="HI_RES_LOSSLESS")
    )
    assert q.ok
    assert q.bit_depth == 24
    assert q.sample_rate == 48000
    assert q.bit_depth_text == "24 Bit"
    assert q.sample_rate_text == "48.0 kHz"
    assert q.summary() == "Hi-Res Lossless · 24 Bit · 48.0 kHz"


def test_extract_none_stream_is_error():
    q = extract_stream_quality(None, fallback_quality="LOSSLESS")
    assert not q.ok
    assert q.error
    assert q.audio_quality == "LOSSLESS"


def test_lossless_summary_has_no_false_bit_depth():
    # 16 Bit/44.1 kHz Lossless
    q = ExactQuality(bit_depth=16, sample_rate=44100, audio_quality="LOSSLESS")
    assert q.summary() == "Lossless · 16 Bit · 44.1 kHz"


def test_album_exact_quality_uses_first_track_stream():
    album = _FakeAlbum(
        [_FakeTrack(_FakeStream(24, 96000, "HI_RES_LOSSLESS"), "HI_RES_LOSSLESS")]
    )
    q = album_exact_quality(_FakeSession(album), "123")
    assert q.bit_depth == 24
    assert q.sample_rate == 96000


def test_album_exact_quality_handles_no_tracks():
    q = album_exact_quality(_FakeSession(_FakeAlbum([])), "123")
    assert not q.ok
    assert q.error


def test_album_exact_quality_handles_stream_error_keeps_tier():
    album = _FakeAlbum([_FakeTrack(RuntimeError("no sub"), "HI_RES_LOSSLESS")])
    q = album_exact_quality(_FakeSession(album), "123")
    assert not q.ok
    assert q.audio_quality == "HI_RES_LOSSLESS"
    assert q.error


def test_album_exact_quality_handles_album_error():
    q = album_exact_quality(_FakeSession(RuntimeError("boom")), "123")
    assert not q.ok
    assert q.error
