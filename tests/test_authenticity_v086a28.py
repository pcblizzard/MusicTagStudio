from __future__ import annotations

from musictagstudio.audio_analysis.authenticity import (
    assess,
    estimate_source_bitrate,
    is_lossless_codec,
)

# Kantenformen: künstliche Brickwall vs. natürlicher Abfall.
_BRICKWALL = {"shelf_db": -110.0, "steepness_db": 80.0}  # steil + digitale Stille
_NATURAL = {"shelf_db": -45.0, "steepness_db": 20.0}  # sanft, Restenergie


def test_genuine_hires_has_ultrasonic_content():
    v = assess(codec="flac", sample_rate=96000, spectral_cutoff_hz=45000.0)
    assert v.level == "genuine"
    assert v.message_key == "auth_genuine_hires"


def test_upsampled_hires_flagged_as_fake():
    v = assess(
        codec="flac", sample_rate=96000, spectral_cutoff_hz=20000.0, **_BRICKWALL
    )
    assert v.level == "fake"
    assert v.message_key == "auth_upsampled"
    assert v.confidence == "high"


def test_upsampled_hires_medium_without_shape():
    # Kein Formsignal, aber 96 kHz ohne Inhalt über 24 kHz bleibt verdächtig.
    v = assess(codec="flac", sample_rate=96000, spectral_cutoff_hz=20000.0)
    assert v.level == "fake"
    assert v.confidence == "medium"


def test_upsampled_hires_cutoff_just_above_threshold_but_brickwall():
    # Realfall 44,1 kHz -> 96 kHz: -60-dB-Schnitt bei 24,2 kHz, aber steile
    # Kante mit fast stiller Region darüber -> muss trotzdem als Fake gelten.
    v = assess(
        codec="flac",
        sample_rate=96000,
        spectral_cutoff_hz=24200.0,
        shelf_db=-75.0,
        steepness_db=55.0,
    )
    assert v.level == "fake"


def test_genuine_hires_natural_rolloff_not_flagged():
    # 96 kHz mit sanftem Abfall (Restenergie, keine Brickwall) -> echt.
    v = assess(
        codec="flac",
        sample_rate=96000,
        spectral_cutoff_hz=40000.0,
        shelf_db=-33.0,
        steepness_db=13.0,
    )
    assert v.level == "genuine"


def test_lossless_cd_with_full_range_is_genuine():
    v = assess(codec="flac", sample_rate=44100, spectral_cutoff_hz=21500.0)
    assert v.level == "genuine"
    assert v.message_key == "auth_genuine_lossless"


def test_lossless_with_mp3_brickwall_is_fake_high():
    v = assess(
        codec="flac", sample_rate=44100, spectral_cutoff_hz=16000.0, **_BRICKWALL
    )
    assert v.level == "fake"
    assert v.confidence == "high"


def test_low_cutoff_but_natural_edge_is_not_fake():
    # Tiefer Schnitt, aber sanfte Kante mit Restenergie -> KEIN Fehlalarm.
    v = assess(
        codec="flac", sample_rate=44100, spectral_cutoff_hz=16000.0, **_NATURAL
    )
    assert v.level == "suspect"
    assert v.confidence == "low"


def test_borderline_cutoff_natural_edge_stays_genuine():
    v = assess(
        codec="flac", sample_rate=44100, spectral_cutoff_hz=18000.0, **_NATURAL
    )
    assert v.level == "genuine"


def test_borderline_cutoff_brickwall_is_fake():
    v = assess(
        codec="flac", sample_rate=44100, spectral_cutoff_hz=18000.0, **_BRICKWALL
    )
    assert v.level == "fake"


def test_lossy_codec_reported_as_lossy():
    v = assess(codec="mp3", sample_rate=44100, spectral_cutoff_hz=16000.0)
    assert v.level == "lossy"


def test_unknown_without_cutoff():
    v = assess(codec="flac", sample_rate=44100, spectral_cutoff_hz=None)
    assert v.level == "unknown"


def test_pcm_and_alac_are_lossless():
    assert is_lossless_codec("pcm_s24le")
    assert is_lossless_codec("alac")
    assert not is_lossless_codec("aac")


def test_source_bitrate_bands():
    assert estimate_source_bitrate(16000.0) == 128
    assert estimate_source_bitrate(19000.0) == 192
    assert estimate_source_bitrate(20500.0) == 320
    assert estimate_source_bitrate(10000.0) == 96
    # Voller Frequenzumfang -> kein typischer Lossy-Lowpass.
    assert estimate_source_bitrate(21500.0) == 0
    assert estimate_source_bitrate(None) == 0
    assert estimate_source_bitrate(0) == 0


def test_fake_mp3_carries_bitrate_estimate():
    v = assess(
        codec="flac", sample_rate=44100, spectral_cutoff_hz=16000.0, **_BRICKWALL
    )
    assert v.level == "fake"
    assert v.estimated_source_kbps == 128


def test_genuine_lossless_has_no_bitrate_estimate():
    v = assess(codec="flac", sample_rate=44100, spectral_cutoff_hz=21500.0)
    assert v.level == "genuine"
    assert v.estimated_source_kbps == 0
