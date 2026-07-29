from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..i18n import tr


class PremiumDialog(QDialog):
    """Freundlicher Hinweis, dass eine Funktion eine Premium-Lizenz braucht.

    ``exec()`` liefert ``QDialog.DialogCode.Accepted``, wenn der Nutzer
    "Lizenzschlüssel eingeben" wählt – der Aufrufer öffnet dann die
    Einstellungen. Der Spenden-Hinweis stellt klar, dass Spenden kein Premium
    freischalten (dafür ist der Lizenzschlüssel da).
    """

    def __init__(
        self,
        parent=None,
        *,
        language: str = "automatic",
        title: str,
        message: str,
        show_enter_license: bool = True,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(title)
        self.setMinimumWidth(470)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        heading = QLabel(f"<h2>💎 {title}</h2>")
        layout.addWidget(heading)

        body = QLabel(message)
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(body)

        hint = QLabel(tr("premium_donation_hint", language))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid); font-size: 11px;")
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        later = QPushButton(tr("premium_later", language))
        later.clicked.connect(self.reject)
        buttons.addWidget(later)
        if show_enter_license:
            enter = QPushButton(tr("premium_enter_license", language))
            enter.setDefault(True)
            enter.clicked.connect(self.accept)
            buttons.addWidget(enter)
        layout.addLayout(buttons)
