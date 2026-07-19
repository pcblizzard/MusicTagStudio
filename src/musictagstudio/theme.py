from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


INPUT_NORMAL = ""

INPUT_CHANGED = """
QLineEdit {
    background: #eaf3ff;
    border: 1px solid #2f80ed;
    border-radius: 6px;
}
"""

BUTTON_NORMAL = "Änderungen speichern"
BUTTON_CHANGED = "Änderungen speichern *"


def apply_theme(
    app: QApplication,
    mode: str,
) -> None:
    resolved_mode = _resolve_theme_mode(
        app,
        mode,
    )
    app.setStyle("Fusion")

    if resolved_mode == "dark":
        app.setPalette(
            _dark_palette()
        )
        app.setStyleSheet(
            _dark_stylesheet()
        )
    else:
        app.setPalette(
            _light_palette()
        )
        app.setStyleSheet(
            _light_stylesheet()
        )


def _resolve_theme_mode(
    app: QApplication,
    mode: str,
) -> str:
    if mode in {
        "light",
        "dark",
    }:
        return mode

    if (
        app.styleHints().colorScheme()
        == Qt.ColorScheme.Dark
    ):
        return "dark"

    return "light"


def _light_palette() -> QPalette:
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#f7f9fc",
        QPalette.ColorRole.WindowText: "#1f2937",
        QPalette.ColorRole.Base: "#ffffff",
        QPalette.ColorRole.AlternateBase: "#f5f7fa",
        QPalette.ColorRole.ToolTipBase: "#ffffff",
        QPalette.ColorRole.ToolTipText: "#1f2937",
        QPalette.ColorRole.Text: "#1f2937",
        QPalette.ColorRole.Button: "#ffffff",
        QPalette.ColorRole.ButtonText: "#1f2937",
        QPalette.ColorRole.BrightText: "#b42318",
        QPalette.ColorRole.Highlight: "#2f80ed",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: "#7b8794",
        QPalette.ColorRole.Mid: "#d7dee7",
        QPalette.ColorRole.Dark: "#aab4c0",
        QPalette.ColorRole.Light: "#ffffff",
    }

    for role, color in colors.items():
        palette.setColor(
            role,
            QColor(color),
        )

    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor("#a2abb5"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor("#a2abb5"),
    )

    return palette


def _dark_palette() -> QPalette:
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#15191d",
        QPalette.ColorRole.WindowText: "#edf2f6",
        QPalette.ColorRole.Base: "#101418",
        QPalette.ColorRole.AlternateBase: "#1b2127",
        QPalette.ColorRole.ToolTipBase: "#222930",
        QPalette.ColorRole.ToolTipText: "#edf2f6",
        QPalette.ColorRole.Text: "#edf2f6",
        QPalette.ColorRole.Button: "#232a31",
        QPalette.ColorRole.ButtonText: "#edf2f6",
        QPalette.ColorRole.BrightText: "#ff8b8b",
        QPalette.ColorRole.Highlight: "#20c7df",
        QPalette.ColorRole.HighlightedText: "#061b20",
        QPalette.ColorRole.PlaceholderText: "#8b98a4",
        QPalette.ColorRole.Mid: "#3a444e",
        QPalette.ColorRole.Dark: "#080b0e",
        QPalette.ColorRole.Light: "#343d46",
    }

    for role, color in colors.items():
        palette.setColor(
            role,
            QColor(color),
        )

    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor("#6f7b85"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor("#6f7b85"),
    )

    return palette


def _light_stylesheet() -> str:
    return """
    QWidget {
        font-family: "Segoe UI";
        font-size: 10pt;
    }
    QMainWindow, QDialog {
        background: #f7f9fc;
    }
    QWidget#mainSidebar {
        background: #fbfcfe;
        border-right: 1px solid #dbe2ea;
    }
    QWidget#mainSidebar QPushButton {
        text-align: left;
        padding: 8px 12px;
        border: 1px solid transparent;
        background: transparent;
    }
    QWidget#mainSidebar QPushButton:hover {
        background: #edf5ff;
        border-color: #d6e6fb;
    }
    QWidget#mainSidebar QPushButton:checked {
        background: #dbeafe;
        color: #174ea6;
        border-color: #b8d4fa;
        font-weight: 600;
    }
    QToolTip {
        color: #1f2937;
        background: #ffffff;
        border: 1px solid #c8d0db;
        border-radius: 5px;
        padding: 6px;
    }
    QGroupBox {
        font-weight: 600;
        border: 1px solid #dbe2ea;
        border-radius: 9px;
        margin-top: 12px;
        padding: 12px 10px 10px 10px;
        background: #ffffff;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 5px;
        color: #334155;
    }
    QPushButton {
        background: #ffffff;
        border: 1px solid #cfd7e2;
        border-radius: 7px;
        padding: 7px 12px;
        min-height: 18px;
    }
    QPushButton:hover {
        background: #edf5ff;
        border-color: #7ab0f5;
    }
    QPushButton:pressed,
    QPushButton:checked {
        background: #dbeafe;
        color: #174ea6;
        border-color: #2f80ed;
    }
    QPushButton:disabled {
        background: #f1f4f8;
        color: #9aa4b2;
        border-color: #e2e7ed;
    }
    QLineEdit, QComboBox, QSpinBox {
        background: #ffffff;
        border: 1px solid #cfd7e2;
        border-radius: 6px;
        padding: 6px 8px;
        selection-background-color: #bcd8ff;
        selection-color: #1f2937;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
        border: 1px solid #2f80ed;
    }
    QLineEdit#mediaSearchField {
        border-radius: 17px;
        padding: 8px 14px;
        font-size: 11pt;
    }
    QListWidget#liveSearchSuggestions {
        border-radius: 12px;
        padding: 5px;
        background: #ffffff;
    }
    QListWidget#liveSearchSuggestions::item {
        border-radius: 7px;
        padding: 9px 11px;
    }
    QListWidget#liveSearchSuggestions::item:hover,
    QListWidget#liveSearchSuggestions::item:selected {
        background: #edf5ff;
        color: #174ea6;
    }
    QPlainTextEdit#lyricsDisplay {
        background: #ffffff;
        border: 1px solid #dbe2ea;
        border-radius: 10px;
        padding: 14px;
        font-family: "Segoe UI";
        font-size: 11pt;
    }
    QLabel#lyricsStatus {
        padding: 7px 9px;
        border-radius: 6px;
        background: #eef2f7;
        color: #475569;
    }
    QLabel#lyricsStatus[statusKind="success"] {
        background: #e7f7ed;
        color: #176b3a;
    }
    QLabel#lyricsStatus[statusKind="offline"],
    QLabel#lyricsStatus[statusKind="error"] {
        background: #fff0f0;
        color: #a12626;
    }
    QLabel#lyricsStatus[statusKind="not_found"],
    QLabel#lyricsStatus[statusKind="incomplete"] {
        background: #fff7df;
        color: #805b00;
    }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    QTableWidget, QTreeWidget, QListWidget, QListView {
        background: #ffffff;
        alternate-background-color: #f5f8fa;
        border: 1px solid #dbe2ea;
        border-radius: 7px;
        gridline-color: #e7ecf2;
        selection-background-color: #dbeafe;
        selection-color: #1f2937;
    }
    QHeaderView::section {
        background: #f0f4f8;
        color: #334155;
        border: none;
        border-right: 1px solid #dce3eb;
        border-bottom: 1px solid #cfd7e2;
        padding: 7px;
        font-weight: 600;
    }
    QMenuBar, QMenu {
        background: #ffffff;
        color: #1f2937;
    }
    QMenuBar::item:selected, QMenu::item:selected {
        background: #e4efff;
        color: #1f2937;
    }
    QToolBar {
        background: #fbfcfe;
        border: none;
        border-bottom: 1px solid #dbe2ea;
        spacing: 5px;
        padding: 6px 10px;
    }
    QToolButton {
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 6px 9px;
        background: transparent;
    }
    QToolButton:hover {
        background: #edf5ff;
        border-color: #c8dcf8;
    }
    QScrollBar:vertical {
        width: 12px;
        background: #f1f4f8;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #c3ccd6;
        border-radius: 6px;
        min-height: 28px;
    }
    QScrollBar::handle:vertical:hover {
        background: #9da8b5;
    }
    QStatusBar {
        background: #ffffff;
        border-top: 1px solid #dbe2ea;
        color: #64748b;
    }
    """


def _dark_stylesheet() -> str:
    return """
    QWidget {
        font-family: "Segoe UI";
        font-size: 10pt;
    }
    QMainWindow, QDialog {
        background: #15191d;
    }
    QToolTip {
        color: #edf2f6;
        background: #222930;
        border: 1px solid #4b5864;
        border-radius: 5px;
        padding: 6px;
    }
    QGroupBox {
        font-weight: 600;
        border: 1px solid #333d46;
        border-radius: 9px;
        margin-top: 12px;
        padding: 12px 10px 10px 10px;
        background: #1b2025;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 5px;
        color: #cfd8df;
    }
    QPushButton {
        background: #242b32;
        border: 1px solid #3b4650;
        border-radius: 7px;
        padding: 7px 12px;
        min-height: 18px;
    }
    QPushButton:hover {
        background: #293840;
        border-color: #28bfd3;
    }
    QPushButton:pressed,
    QPushButton:checked {
        background: #20c7df;
        color: #062129;
        border-color: #20c7df;
    }
    QPushButton:disabled {
        background: #1c2227;
        color: #68737d;
        border-color: #293139;
    }
    QLineEdit, QComboBox, QSpinBox {
        background: #101418;
        border: 1px solid #3b4650;
        border-radius: 6px;
        padding: 6px 8px;
        selection-background-color: #20c7df;
        selection-color: #062129;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
        border: 1px solid #20c7df;
    }
    QLineEdit#mediaSearchField {
        border-radius: 17px;
        padding: 8px 14px;
        font-size: 11pt;
        background: #1c2024;
    }
    QListWidget#liveSearchSuggestions {
        border: 1px solid #3a424a;
        border-radius: 12px;
        padding: 5px;
        background: #202327;
    }
    QListWidget#liveSearchSuggestions::item {
        border-radius: 7px;
        padding: 9px 11px;
    }
    QListWidget#liveSearchSuggestions::item:hover,
    QListWidget#liveSearchSuggestions::item:selected {
        background: #30363c;
        color: #ffffff;
    }
    QPlainTextEdit#lyricsDisplay {
        background: #101418;
        border: 1px solid #303a43;
        border-radius: 10px;
        padding: 14px;
        font-family: "Segoe UI";
        font-size: 11pt;
    }
    QLabel#lyricsStatus {
        padding: 7px 9px;
        border-radius: 6px;
        background: #20272d;
        color: #b8c4cd;
    }
    QLabel#lyricsStatus[statusKind="success"] {
        background: #173a29;
        color: #8ee0ad;
    }
    QLabel#lyricsStatus[statusKind="offline"],
    QLabel#lyricsStatus[statusKind="error"] {
        background: #402326;
        color: #ffaaaa;
    }
    QLabel#lyricsStatus[statusKind="not_found"],
    QLabel#lyricsStatus[statusKind="incomplete"] {
        background: #3b321b;
        color: #f1cd72;
    }
    QComboBox::drop-down {
        border: none;
        width: 24px;
    }
    QTableWidget, QTreeWidget, QListWidget, QListView {
        background: #101418;
        alternate-background-color: #171d22;
        border: 1px solid #303a43;
        border-radius: 7px;
        gridline-color: #293139;
        selection-background-color: #245f6a;
        selection-color: #f5fbfc;
    }
    QHeaderView::section {
        background: #252c33;
        color: #dce4ea;
        border: none;
        border-right: 1px solid #343f49;
        border-bottom: 1px solid #3a4650;
        padding: 7px;
        font-weight: 600;
    }
    QMenuBar, QMenu {
        background: #1b2025;
        color: #edf2f6;
    }
    QMenuBar::item:selected, QMenu::item:selected {
        background: #285c66;
    }
    QToolBar {
        background: #1b2025;
        border: none;
        border-bottom: 1px solid #303a43;
        spacing: 4px;
        padding: 5px 8px;
    }
    QToolButton {
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 6px 9px;
        background: transparent;
    }
    QToolButton:hover {
        background: #28343b;
        border-color: #2a6873;
    }
    QScrollBar:vertical {
        width: 12px;
        background: #171c21;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #44515c;
        border-radius: 6px;
        min-height: 28px;
    }
    QScrollBar::handle:vertical:hover {
        background: #5a6975;
    }
    QStatusBar {
        background: #1b2025;
        border-top: 1px solid #303a43;
        color: #9cabb6;
    }
    """
