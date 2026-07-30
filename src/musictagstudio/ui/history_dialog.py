from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QListWidget,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from pathlib import Path

from ..history import FileChanges, HistoryEntry
from ..i18n import tr, tr_plural


class HistoryDialog(QDialog):
    """Report: listet Vorgänge und zeigt je Vorgang die feldgenauen Änderungen."""

    def __init__(
        self,
        entries: list[HistoryEntry],
        parent=None,
        *,
        language: str = "automatic",
        describe: Callable[[HistoryEntry], list[FileChanges]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self._entries = entries
        self._describe = describe
        self.setWindowTitle(tr("history", language))
        self.resize(820, 480)

        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.list = QListWidget()
        if not entries:
            self.list.addItem(tr("history_empty", language))
        else:
            for entry in entries:
                # description ist ein i18n-Key; alte Roh-Texte geben ihren Wert
                # unveraendert zurueck (tr faellt auf den Key zurueck).
                self.list.addItem(
                    f"{entry.created_at} · "
                    f"{tr(entry.description, language)} · "
                    f"{tr_plural('history_files', len(entry.files), language)}"
                )
        self.list.currentRowChanged.connect(self._show_details)
        splitter.addWidget(self.list)

        self.details = QTreeWidget()
        self.details.setColumnCount(3)
        self.details.setHeaderLabels(
            [
                tr("history_col_field", language),
                tr("history_col_before", language),
                tr("history_col_after", language),
            ]
        )
        header = self.details.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.details)
        splitter.setSizes([300, 520])
        layout.addWidget(splitter)

        self.hint = QLabel(tr("history_select_entry", language))
        self.hint.setStyleSheet("color: palette(mid);")
        layout.addWidget(self.hint)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        if entries:
            self.list.setCurrentRow(0)

    def _show_details(self, row: int) -> None:
        self.details.clear()
        if self._describe is None or not (0 <= row < len(self._entries)):
            return
        entry = self._entries[row]
        changes = self._describe(entry)
        if not changes:
            self.hint.setText(tr("history_no_changes", self.language))
            return
        self.hint.setText("")

        for file_change in changes:
            name = Path(file_change.path).name
            parent = QTreeWidgetItem([name, "", ""])
            parent.setFirstColumnSpanned(True)
            self.details.addTopLevelItem(parent)

            if file_change.rename is not None:
                old, new = file_change.rename
                parent.addChild(
                    QTreeWidgetItem(
                        [tr("history_rename", self.language),
                         Path(old).name, Path(new).name]
                    )
                )
            for field, old, new in file_change.field_changes:
                parent.addChild(QTreeWidgetItem([field, old, new]))
            if file_change.cover_changed:
                parent.addChild(
                    QTreeWidgetItem([tr("history_cover", self.language), "", ""])
                )
            parent.setExpanded(True)
