from pathlib import Path


def test_tagger_buttons_have_clear_action_labels():
    text = (
        Path(__file__).parents[1]
        / "src" / "musictagstudio" / "ui" / "main_window.py"
    ).read_text(encoding="utf-8")
    assert 'tr("search_metadata_title"' in text  # i18n-Keys statt Fixtext
    assert 'tr("search_metadata_selection"' in text
    assert 'tr("load_direct"' in text
    assert "def resizeEvent" in text
    assert "def _layout_provider_buttons" in text


def test_high_dpi_rounding_policy_is_enabled():
    text = (
        Path(__file__).parents[1]
        / "src" / "musictagstudio" / "main.py"
    ).read_text(encoding="utf-8")
    assert "HighDpiScaleFactorRoundingPolicy.PassThrough" in text
