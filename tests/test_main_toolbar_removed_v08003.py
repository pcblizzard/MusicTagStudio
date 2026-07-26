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

    assert 'tr("file", self.language)' in text
    assert 'tr("add_folder", self.language)' in text
    assert 'tr("rescan", self.language)' in text
    assert 'tr("edit", self.language)' in text
    assert 'tr("undo", self.language)' in text  # i18n statt Fixtext
    assert 'tr("redo", self.language)' in text
