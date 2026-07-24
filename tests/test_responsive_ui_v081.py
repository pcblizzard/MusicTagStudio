from pathlib import Path


def test_tagger_buttons_have_clear_action_labels():
    text = (
        Path(__file__).parents[1]
        / "src" / "musictagstudio" / "ui" / "main_window.py"
    ).read_text(encoding="utf-8")
    assert '"Metadaten für Titel suchen"' in text
    assert '"Metadaten für Auswahl suchen"' in text
    assert '"Album/Song über Link oder ID laden"' in text
    assert "def resizeEvent" in text
    assert "def _layout_provider_buttons" in text


def test_high_dpi_rounding_policy_is_enabled():
    text = (
        Path(__file__).parents[1]
        / "src" / "musictagstudio" / "main.py"
    ).read_text(encoding="utf-8")
    assert "HighDpiScaleFactorRoundingPolicy.PassThrough" in text
