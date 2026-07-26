from pathlib import Path


def test_discogs_is_integrated_without_a_separate_search_mode():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "media_library_widget.py"
    ).read_text(encoding="utf-8")

    assert "self.search_mode_combo" not in text
    assert "_fetch_discogs_catalog" in text
    assert "_merge_release_groups" in text


def test_discogs_token_field_is_available_in_settings_ui():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "settings_dialog.py"
    ).read_text(encoding="utf-8")

    # Discogs-Token-Label ist jetzt i18n-basiert (tr("discogs_token_label")).
    assert '"discogs_token_label"' in text
    assert "self.discogs_token_edit" in text
