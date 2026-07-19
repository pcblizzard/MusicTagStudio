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


def test_metadata_panel_is_not_fixed_width():
    text = source()

    assert "right_widget.setFixedWidth" not in text
    assert "right_widget.setMinimumWidth" in text
    assert "right_widget.setMaximumWidth" in text
    assert "self.workspace_stack.setMinimumWidth" in text


def test_settings_is_not_in_sidebar_and_is_in_file_menu():
    text = source()

    workspace_block = text[
        text.index("workspace_pages = ("):
        text.index("for name, index in workspace_pages")
    ]
    assert '("Einstellungen", 4)' not in workspace_block
    assert 'tr("settings", self.language)' in text
    assert "self.switch_workspace(\n                4" in text


def test_exit_is_last_file_menu_command():
    text = source()

    assert 'tr("exit", self.language)' in text
    assert "QKeySequence.StandardKey.Quit" in text
    assert "exit_action.triggered.connect(\n            self.close" in text
