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
    assert "Musikquelle nicht gefunden" in text
    assert "Bereits indizierte Alben bleiben" in text
