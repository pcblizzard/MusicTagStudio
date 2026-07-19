from pathlib import Path


def test_media_library_has_debug_panel_and_new_controller():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "media_library_widget.py"
    ).read_text(encoding="utf-8")

    assert "self.catalog_controller" in text
    assert "self.debug_button" in text
    assert "self.debug_output" in text
    assert "trace.as_text()" in text
