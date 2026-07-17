from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class ChangePreviewDialog(QDialog):
    def __init__(
        self,
        changes: list[
            tuple[str, str, str, str]
        ],
        parent=None,
    ) -> None:
        super().__init__(
            parent
        )
        self.setWindowTitle(
            "Änderungsvorschau"
        )
        self.resize(
            950,
            520,
        )

        layout = QVBoxLayout(
            self
        )
        layout.addWidget(
            QLabel(
                f"{len(changes)} Änderung(en) werden geschrieben."
            )
        )

        table = QTableWidget(
            len(changes),
            4,
        )
        table.setHorizontalHeaderLabels(
            [
                "Datei/Titel",
                "Feld",
                "Vorher",
                "Nachher",
            ]
        )

        for row, (
            subject,
            field,
            before,
            after,
        ) in enumerate(changes):
            for column, value in enumerate(
                (
                    subject,
                    field,
                    before,
                    after,
                )
            ):
                table.setItem(
                    row,
                    column,
                    QTableWidgetItem(
                        value
                    ),
                )

        table.resizeColumnsToContents()
        layout.addWidget(
            table
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(
            QDialogButtonBox.StandardButton.Save
        ).setText(
            "Änderungen schreiben"
        )
        buttons.accepted.connect(
            self.accept
        )
        buttons.rejected.connect(
            self.reject
        )
        layout.addWidget(
            buttons
        )
