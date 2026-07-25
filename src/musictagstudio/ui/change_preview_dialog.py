from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


def _summary_text(
    changes: list[tuple[str, str, str, str]],
    file_count: int | None,
) -> str:
    """Beschreibt Feldänderungen und die Zahl betroffener Titel eindeutig."""
    change_count = len(changes)

    if file_count is None:
        file_count = len({subject for subject, _f, _b, _a in changes})

    changes_word = "Änderung" if change_count == 1 else "Änderungen"
    titles_word = "Titel" if file_count == 1 else "Titeln"
    verb = "wird" if change_count == 1 else "werden"

    return (
        f"{change_count} {changes_word} an {file_count} "
        f"{titles_word} {verb} geschrieben."
    )


class ChangePreviewDialog(QDialog):
    def __init__(
        self,
        changes: list[
            tuple[str, str, str, str]
        ],
        parent=None,
        *,
        file_count: int | None = None,
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
                _summary_text(changes, file_count)
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
