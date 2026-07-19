from pathlib import Path


def test_responsive_grid_layout_is_imported():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "QGridLayout," in text
    assert "self.provider_buttons_layout = QGridLayout()" in text
