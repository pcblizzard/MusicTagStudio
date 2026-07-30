from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..i18n import tr
from ..purchase import configured_options


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

        self._add_purchase_section(layout)

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

    def _add_purchase_section(self, layout: QVBoxLayout) -> None:
        """Festpreis-Kauf-Buttons je Laufzeit (nur eingerichtete anzeigen)."""
        options = configured_options()
        if not options:
            return

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: palette(mid);")
        layout.addWidget(line)

        heading = QLabel(f"<b>{tr('premium_buy_heading', self.language)}</b>")
        layout.addWidget(heading)

        row = QHBoxLayout()
        for option in options:
            label = tr(option.label_key, self.language)
            if option.price:
                label = f"{label} · {option.price}"
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, url=option.url: QDesktopServices.openUrl(
                    QUrl(url)
                )
            )
            row.addWidget(button)
        layout.addLayout(row)

        buy_hint = QLabel(tr("premium_buy_hint", self.language))
        buy_hint.setWordWrap(True)
        buy_hint.setStyleSheet("color: palette(mid); font-size: 11px;")
        layout.addWidget(buy_hint)
