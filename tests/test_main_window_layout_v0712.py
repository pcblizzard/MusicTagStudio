from pathlib import Path


def source_text() -> str:
    path = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    )

    return path.read_text(encoding="utf-8")


def test_comment_field_is_visible():
    text = source_text()

    assert '"comment",' in text
    assert '"comment": "Kommentar:"' in text


def test_columns_are_interactive_and_persistent():
    text = source_text()

    assert "QHeaderView.ResizeMode.Interactive" in text
    assert "QSettings(" in text
    assert "main_table/column_widths" in text
    assert "Spaltenbreiten zurücksetzen" in text


def test_editor_is_scrollable():
    text = source_text()

    assert "QScrollArea" in text
    assert "self.editor_scroll" in text
