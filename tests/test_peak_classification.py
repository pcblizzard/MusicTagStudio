from musictagstudio.audio_analysis.analyzer import (
    classify_true_peak,
)


def test_true_peak_classification():
    assert classify_true_peak(None) == "unknown"
    assert classify_true_peak(-1.5) == "normal"
    assert classify_true_peak(-0.5) == "elevated"
    assert classify_true_peak(0.7) == "over_zero"
    assert classify_true_peak(2.1) == "critical"
