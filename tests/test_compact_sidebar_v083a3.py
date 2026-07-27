from pathlib import Path


def test_sidebar_and_workspace_buttons_are_compact():
    source = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    # Die Sidebar-Breite wird jetzt adaptiv aus der Textbreite berechnet
    # (Sprache + Schriftgroesse), mit kompaktem Minimum statt fester Zahl.
    assert "sidebar.setFixedWidth(max(180, widest_text + 78))" in source
    assert "button.setMinimumHeight(\n                34" in source
    assert "sidebar_layout.setContentsMargins(\n            8," in source
