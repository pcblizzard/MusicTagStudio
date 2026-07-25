import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from musictagstudio.ui.main_window import MainWindow


def test_settings_workspace_clears_sidebar_selection_and_updates_status():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    settings_button = window.workspace_buttons.button(4)
    assert settings_button is None

    window.switch_workspace(4)
    app.processEvents()

    assert window.workspace_stack.currentIndex() == 4
    assert window.workspace_buttons.checkedButton() is None
    assert window.statusBar().currentMessage() == "Einstellungen"

    window.close()
    app.processEvents()


def test_initial_dashboard_selection_matches_visible_workspace():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.workspace_stack.currentIndex() == 5
    assert window.workspace_buttons.button(5).isChecked()
    assert window.statusBar().currentMessage() == "Startseite"

    window.close()
    app.processEvents()
