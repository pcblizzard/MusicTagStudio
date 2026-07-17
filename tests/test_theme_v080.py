from pathlib import Path


def test_light_theme_is_custom_and_not_standard_palette_only():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "theme.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "def _light_palette" in text
    assert "def _light_stylesheet" in text
    assert "#f7f9fc" in text
    assert "#2f80ed" in text


def test_dark_theme_is_custom():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "theme.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "def _dark_stylesheet" in text
    assert "#15191d" in text
