from pathlib import Path


def source() -> str:
    return (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(
        encoding="utf-8"
    )


def test_main_toolbar_is_completely_removed():
    text = source()

    assert "QToolBar" not in text
    assert "def create_toolbar" not in text
    assert '"Hauptfunktionen"' not in text
    assert "self.addToolBar" not in text


def test_file_and_edit_commands_are_in_menus():
    text = source()

    assert 'addMenu(\n            "Datei"' in text
    assert '"Ordner hinzufügen …"' in text
    assert '"Neu einlesen"' in text
    assert 'addMenu(\n            "Bearbeiten"' in text
    assert '"Rückgängig"' in text
    assert '"Wiederholen"' in text
