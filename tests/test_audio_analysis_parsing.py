import math

from musictagstudio.audio_analysis.analyzer import (
    calculate_replaygain,
    db_to_linear,
    parse_loudnorm_output,
    parse_probe_payload,
)


def test_parse_probe_payload():
    result = parse_probe_payload(
        "song.flac",
        {
            "format": {
                "format_name": "flac",
                "duration": "123.4",
                "size": "12345678",
                "bit_rate": "800000",
            },
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "flac",
                    "sample_rate": "44100",
                    "bits_per_raw_sample": "16",
                    "channels": 2,
                    "channel_layout": "stereo",
                }
            ],
        },
    )

    assert result.codec == "flac"
    assert result.sample_rate == 44100
    assert result.bit_depth == 16
    assert result.channels == 2
    assert result.duration_seconds == 123.4


def test_parse_loudnorm_output():
    stderr = """
    Some FFmpeg output
    {
        "input_i" : "-10.25",
        "input_tp" : "-0.12",
        "input_lra" : "6.70",
        "input_thresh" : "-20.40",
        "output_i" : "-18.00"
    }
    """

    result = parse_loudnorm_output(stderr)

    assert result["input_i"] == -10.25
    assert result["input_tp"] == -0.12
    assert result["input_lra"] == 6.70


def test_replaygain_calculation():
    assert calculate_replaygain(-10.0) == -8.0


def test_db_to_linear():
    assert math.isclose(
        db_to_linear(0.0),
        1.0,
    )
