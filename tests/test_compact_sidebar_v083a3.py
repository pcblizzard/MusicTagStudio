from pathlib import Path


def test_sidebar_and_workspace_buttons_are_compact():
    source = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert "sidebar.setFixedWidth(\n            168" in source
    assert "button.setMinimumHeight(\n                34" in source
    assert "sidebar_layout.setContentsMargins(\n            8," in source
