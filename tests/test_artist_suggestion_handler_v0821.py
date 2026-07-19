from pathlib import Path


def test_artist_suggestion_handler_exists_and_is_connected():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "media_library_widget.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "self._use_artist_suggestion" in text
    assert "def _use_artist_suggestion" in text
    assert "self.search_edit.setText" in text
    assert "self.search()" in text
