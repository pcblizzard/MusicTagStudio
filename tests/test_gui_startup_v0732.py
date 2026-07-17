import os

import pytest

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

pytest.importorskip(
    "PySide6"
)

from PySide6.QtWidgets import QApplication

from musictagstudio.ui.main_window import MainWindow


def test_main_window_starts_and_all_workspaces_can_open():
    app = (
        QApplication.instance()
        or QApplication([])
    )
    window = MainWindow()

    assert window is not None
    assert window.workspace_stack.count() >= 5

    for index in range(
        window.workspace_stack.count()
    ):
        window.switch_workspace(
            index
        )
        app.processEvents()

    window.close()
    app.processEvents()
