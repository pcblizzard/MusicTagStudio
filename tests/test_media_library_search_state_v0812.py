from pathlib import Path


def test_search_has_visible_suggestion_and_error_states():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "media_library_widget.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "self.suggestion_label" in text
    assert "Kein exakter Treffer." in text
    assert "Keine Treffer gefunden" in text
    assert "Suche fehlgeschlagen" in text
