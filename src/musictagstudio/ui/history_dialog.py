from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QVBoxLayout,
)

from ..history import HistoryEntry


class HistoryDialog(QDialog):
    def __init__(
        self,
        entries: list[
            HistoryEntry
        ],
        parent=None,
    ) -> None:
        super().__init__(
            parent
        )
        self.setWindowTitle(
            "Änderungsverlauf"
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
                "In dieser Sitzung wurden noch keine Änderungen geschrieben."
            )
        else:
            for entry in entries:
                items.addItem(
                    f"{entry.created_at} · "
                    f"{entry.description} · "
                    f"{len(entry.files)} Datei(en)"
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
