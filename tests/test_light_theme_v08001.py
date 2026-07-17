from pathlib import Path


def test_light_theme_uses_calm_blue_windows_palette():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "theme.py"
    ).read_text(encoding="utf-8")

    assert "#f7f9fc" in text
    assert "#2f80ed" in text
    assert "#dbeafe" in text
    assert "QWidget#mainSidebar" in text
