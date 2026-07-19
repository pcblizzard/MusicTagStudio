from pathlib import Path


def test_tagger_buttons_have_compact_ellipsis_labels():
    text = (
        Path(__file__).parents[1]
        / "src" / "musictagstudio" / "ui" / "main_window.py"
    ).read_text(encoding="utf-8")
    assert '"Vorschlag …"' in text
    assert '"Mehrfachvorschlag …"' in text
    assert "def resizeEvent" in text
    assert "def _layout_provider_buttons" in text


def test_high_dpi_rounding_policy_is_enabled():
    text = (
        Path(__file__).parents[1]
        / "src" / "musictagstudio" / "main.py"
    ).read_text(encoding="utf-8")
    assert "HighDpiScaleFactorRoundingPolicy.PassThrough" in text
