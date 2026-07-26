from pathlib import Path


def test_dashboard_has_no_duplicate_quick_access():
    text = (
        Path(__file__).parents[1]
        / "src" / "musictagstudio" / "ui" / "dashboard_widget.py"
    ).read_text(encoding="utf-8")
    assert '"Schnellzugriff"' not in text
    # "Musikquelle hinzufuegen" ist jetzt i18n-basiert (tr("add_music_source")).
    assert 'tr("add_music_source"' in text
