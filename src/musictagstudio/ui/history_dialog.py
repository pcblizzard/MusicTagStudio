from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QVBoxLayout,
)

from ..history import HistoryEntry
from ..i18n import tr, tr_plural


class HistoryDialog(QDialog):
    def __init__(
        self,
        entries: list[
            HistoryEntry
        ],
        parent=None,
        *,
        language: str = "automatic",
    ) -> None:
        super().__init__(
            parent
        )
        self.setWindowTitle(
            tr("history", language)
        )
        self.resize(
            650,
            420,
        )

        layout = QVBoxLayout(
            self
        )
        items = QListWidget()

        if not entries:
            items.addItem(
                tr("history_empty", language)
            )
        else:
            for entry in entries:
                # entry.description ist ein i18n-Key; alte Roh-Texte geben ihren
                # Wert unveraendert zurueck (tr faellt auf den Key zurueck).
                items.addItem(
                    f"{entry.created_at} · "
                    f"{tr(entry.description, language)} · "
                    f"{tr_plural('history_files', len(entry.files), language)}"
                )

        layout.addWidget(
            items
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(
            self.reject
        )
        buttons.accepted.connect(
            self.accept
        )
        layout.addWidget(
            buttons
        )
