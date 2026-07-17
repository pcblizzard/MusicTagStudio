from pathlib import Path


def test_library_audit_imports_qt_for_embedded_widget_mode():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "library_audit_dialog.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "Qt.WindowType.Widget" in text
    core_import = text.split(
        "from PySide6.QtCore import (",
        1,
    )[1].split(
        ")",
        1,
    )[0]

    assert "Qt," in core_import
