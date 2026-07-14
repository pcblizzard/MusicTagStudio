from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


INPUT_NORMAL = ""

INPUT_CHANGED = """
QLineEdit {
    background-color: #2f3f52;
    border: 1px solid #5ea3ff;
    border-radius: 4px;
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

    if resolved_mode == "dark":
        app.setPalette(_dark_palette())
        app.setStyleSheet(
            """
            QToolTip {
                color: #f2f2f2;
                background-color: #2b2b2b;
                border: 1px solid #666666;
                padding: 6px;
            }
            """
        )
    else:
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet(
            """
            QToolTip {
                color: #202020;
                background-color: #fffbe6;
                border: 1px solid #9a9a9a;
                padding: 6px;
            }
            """
        )


def _resolve_theme_mode(
    app: QApplication,
    mode: str,
) -> str:
    if mode in {"light", "dark"}:
        return mode

    color_scheme = app.styleHints().colorScheme()

    if color_scheme == Qt.ColorScheme.Dark:
        return "dark"

    return "light"


def _dark_palette() -> QPalette:
    palette = QPalette()

    palette.setColor(
        QPalette.ColorRole.Window,
        QColor(30, 30, 30),
    )
    palette.setColor(
        QPalette.ColorRole.WindowText,
        QColor(240, 240, 240),
    )
    palette.setColor(
        QPalette.ColorRole.Base,
        QColor(24, 24, 24),
    )
    palette.setColor(
        QPalette.ColorRole.AlternateBase,
        QColor(38, 38, 38),
    )
    palette.setColor(
        QPalette.ColorRole.ToolTipBase,
        QColor(43, 43, 43),
    )
    palette.setColor(
        QPalette.ColorRole.ToolTipText,
        QColor(240, 240, 240),
    )
    palette.setColor(
        QPalette.ColorRole.Text,
        QColor(240, 240, 240),
    )
    palette.setColor(
        QPalette.ColorRole.Button,
        QColor(45, 45, 45),
    )
    palette.setColor(
        QPalette.ColorRole.ButtonText,
        QColor(240, 240, 240),
    )
    palette.setColor(
        QPalette.ColorRole.BrightText,
        QColor(255, 90, 90),
    )
    palette.setColor(
        QPalette.ColorRole.Highlight,
        QColor(60, 120, 190),
    )
    palette.setColor(
        QPalette.ColorRole.HighlightedText,
        QColor(255, 255, 255),
    )

    return palette
