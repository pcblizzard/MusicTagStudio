from pathlib import Path


def test_discogs_controls_are_not_visible():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "media_library_widget.py"
    ).read_text(encoding="utf-8")

    assert '"Discogs ergänzen"' not in text
    assert "self.search_mode_combo" not in text
    assert '"Discogs-Token fehlt"' not in text


def test_discogs_token_field_is_not_in_settings_ui():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "settings_dialog.py"
    ).read_text(encoding="utf-8")

    assert '"Discogs-Token:"' not in text
    assert "self.discogs_token_edit" not in text
