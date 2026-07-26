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


def test_toolbar_buttons_have_unique_non_empty_labels():
    app = (
        QApplication.instance()
        or QApplication([])
    )
    window = MainWindow()

    buttons = (
        window.select_button,
        window.scan_button,
        window.direct_album_button,
        *window.provider_action_buttons,
        window.lyrics_search_button,
        window.undo_button,
        window.redo_button,
        window.history_button,
    )

    labels = [button.text().strip() for button in buttons]
    tooltips = [button.toolTip().strip() for button in buttons if button.toolTip().strip()]

    # Kein Knopf darf ohne Beschriftung sein.
    assert all(labels), f"Leere Button-Beschriftung: {labels}"
    # Beschriftungen müssen eindeutig sein, damit sich kein Kopier-/
    # Positionsfehler wie früher (zweimal "BBCode-Text erstellen") einschleicht.
    assert len(set(labels)) == len(labels), f"Doppelte Labels: {labels}"
    # Gesetzte Tooltips dürfen ebenfalls nicht doppelt einem falschen Knopf
    # zugeordnet sein.
    assert len(set(tooltips)) == len(tooltips), f"Doppelte Tooltips: {tooltips}"

    window.close()
    app.processEvents()
