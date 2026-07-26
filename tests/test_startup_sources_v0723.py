from pathlib import Path


def test_main_window_loads_sources_at_startup():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "QTimer.singleShot" in text
    assert "def load_configured_sources" in text
    assert "def scan_configured_sources" in text
    # Offline-Quellen-Hinweis ist i18n-basiert (tr-Keys statt Fixtext).
    assert 'tr("source_missing_title"' in text
    assert 'tr("source_missing_msg"' in text
