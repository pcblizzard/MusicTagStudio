from pathlib import Path


def test_dashboard_has_no_duplicate_quick_access():
    text = (
        Path(__file__).parents[1]
        / "src" / "musictagstudio" / "ui" / "dashboard_widget.py"
    ).read_text(encoding="utf-8")
    assert '"Schnellzugriff"' not in text
    assert '"Musikquelle hinzufügen …"' in text
