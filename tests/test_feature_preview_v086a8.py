import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from musictagstudio.settings import AppSettings
from musictagstudio.ui.settings_dialog import SettingsDialog


def test_feature_handling_preview_follows_all_three_options():
    app = QApplication.instance() or QApplication([])
    dialog = SettingsDialog(AppSettings(), embedded=True)
    source = "Ausgang: 2Pac feat. Dr. Dre - California Love\n"
    expected = {
        "artist_only": (
            source
            + "Titel: California Love\n"
            "Künstler: 2Pac, Dr. Dre"
        ),
        "title_and_artist": (
            source
            + "Titel: California Love (feat. Dr. Dre)\n"
            "Künstler: 2Pac, Dr. Dre"
        ),
        "source": (
            source
            + "Titel: California Love (feat. Dr. Dre)\n"
            "Künstler: 2Pac"
        ),
    }

    for mode, preview in expected.items():
        dialog.feature_combo.setCurrentIndex(
            dialog.feature_combo.findData(mode)
        )
        assert dialog.feature_preview.text() == preview

    dialog.close()
    app.processEvents()
