from pathlib import Path


def test_main_window_contains_workspace_navigation():
    path = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    )
    text = path.read_text(
        encoding="utf-8"
    )

    assert "QStackedWidget" in text
    # Navigation ist i18n-basiert: der Medienbibliotheks-Key statt Fixtext.
    assert '"media_library"' in text
    assert "workspace_pages" in text
    assert "MediaLibraryWidget" in text
    assert "def switch_workspace" in text
