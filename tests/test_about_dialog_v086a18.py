from __future__ import annotations

from PySide6.QtWidgets import QApplication

from musictagstudio import __version__
from musictagstudio.ui.about_dialog import (
    PUBLIC_INTERFACES,
    AboutDialog,
    about_html,
    contributors_html,
    debug_information,
)


def test_about_content_contains_version_interfaces_and_contributor() -> None:
    about = about_html()
    contributors = contributors_html()

    assert __version__ in about
    assert "Genius API" in PUBLIC_INTERFACES
    assert "LRCLIB API" in about
    assert "GPL-3.0-or-later" in about
    assert "pcblizzard" in contributors


def test_debug_information_contains_runtime_versions() -> None:
    debug = debug_information()

    assert f"MusicTagStudio - Version {__version__}" in debug
    assert "Python " in debug
    assert "PySide6 " in debug
    assert "Qt " in debug
    assert "Betriebssystem:" in debug
    assert "CPU-Architektur:" in debug
    assert "Kryptographische Bibliothek:" in debug
    assert "Konfigurierte Online-Anbieter:" in debug
    assert "Streaming-Cache:" in debug
    assert "Client Secret" not in debug


def test_about_dialog_has_three_tabs() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = AboutDialog()

    assert dialog.tabs.count() == 3
    assert [dialog.tabs.tabText(index) for index in range(3)] == [
        "Über",
        "Mitwirkende",
        "Debug-Info",
    ]
    dialog.close()
    assert application is not None
