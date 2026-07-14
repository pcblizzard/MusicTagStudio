from musictagstudio.audio_analysis.models import (
    AudioAnalysisResult,
)
from musictagstudio.audio_analysis.replaygain import (
    replaygain_values,
)


def test_replaygain_values():
    result = AudioAnalysisResult(
        path="song.flac",
        replaygain_track_gain_db=-5.432,
        replaygain_track_peak=0.987654321,
        replaygain_album_gain_db=-4.25,
        replaygain_album_peak=1.0,
    )

    values = replaygain_values(result)

    assert (
        values["REPLAYGAIN_TRACK_GAIN"]
        == "-5.43 dB"
    )
    assert (
        values["REPLAYGAIN_TRACK_PEAK"]
        == "0.98765432"
    )
    assert (
        values["REPLAYGAIN_ALBUM_GAIN"]
        == "-4.25 dB"
    )
