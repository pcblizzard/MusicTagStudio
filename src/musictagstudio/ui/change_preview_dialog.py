from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..i18n import tr, tr_plural


def _summary_text(
    changes: list[tuple[str, str, str, str]],
    file_count: int | None,
    language: str = "automatic",
) -> str:
    """Beschreibt Feldänderungen und die Zahl betroffener Titel eindeutig."""
    change_count = len(changes)

    if file_count is None:
        file_count = len({subject for subject, _f, _b, _a in changes})

    titles = tr_plural("preview_titles", file_count, language)
    return tr_plural("preview_write", change_count, language, titles=titles)


class ChangePreviewDialog(QDialog):
    def __init__(
        self,
        changes: list[
            tuple[str, str, str, str]
        ],
        parent=None,
        *,
        file_count: int | None = None,
        language: str = "automatic",
    ) -> None:
        super().__init__(
            parent
        )
        self.setWindowTitle(
            tr("change_preview_title", language)
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
                _summary_text(changes, file_count, language)
            )
        )

        table = QTableWidget(
            len(changes),
            4,
        )
        table.setHorizontalHeaderLabels(
            [
                tr("col_file_title", language),
                tr("col_field", language),
                tr("col_before", language),
                tr("col_after", language),
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
            tr("write_changes", language)
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
