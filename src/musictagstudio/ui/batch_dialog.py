from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..core.merger import song_values
from ..models.metadata import MergedMetadata
from ..models.song import Song


class BatchComparisonDialog(QDialog):
    def __init__(self, proposals: list[tuple[int, Song, MergedMetadata]], parent=None):
        super().__init__(parent)
        self.proposals = proposals
        self.selected_rows: set[int] = set()
        self.setWindowTitle("Albumvorschläge prüfen")
        self.resize(1200, 650)
        layout = QVBoxLayout(self)
        info = QLabel(
            "Jede markierte Zeile übernimmt alle dort erkannten Änderungen und speichert sie erst nach deiner ausdrücklichen Bestätigung."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget(len(proposals), 7)
        self.table.setHorizontalHeaderLabels(
            ["Speichern", "Track", "Aktueller Titel", "Vorgeschlagener Titel", "Künstler", "Album", "Änderungen"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, (_, song, merged) in enumerate(proposals):
            local = song_values(song)
            changed = merged.changed_fields(local)
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked if changed else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(song.track))
            self.table.setItem(row, 2, QTableWidgetItem(song.title))
            self.table.setItem(row, 3, QTableWidgetItem(merged.values.get("title", song.title)))
            self.table.setItem(row, 4, QTableWidgetItem(merged.values.get("artist", song.artist)))
            self.table.setItem(row, 5, QTableWidgetItem(merged.values.get("album", song.album)))
            self.table.setItem(row, 6, QTableWidgetItem(", ".join(changed)))

        header = self.table.horizontalHeader()
        for column in (0, 1):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(2, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button:
            save_button.setText("Markierte Vorschläge speichern")
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_selection(self):
        self.selected_rows = {
            row
            for row in range(len(self.proposals))
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked
        }
        self.accept()
