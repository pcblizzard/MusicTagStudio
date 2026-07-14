from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..core.merger import song_values
from ..models.metadata import EDITABLE_FIELDS, FIELD_LABELS, MergedMetadata
from ..models.song import Song


SOURCE_LABELS = {
    "local": "Lokal",
    "apple_music": "Apple Music",
    "musicbrainz": "MusicBrainz",
}


class ComparisonDialog(QDialog):
    def __init__(
        self,
        song: Song,
        merged: MergedMetadata,
        warnings: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.song = song
        self.merged = merged
        self.selected_fields: set[str] = set()

        self.setWindowTitle("Metadaten vergleichen")
        self.resize(980, 620)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Wähle aus, welche vorgeschlagenen Werte in den Editor "
            "übernommen werden. Erst der spätere Klick auf "
            "„Änderungen speichern“ schreibt in die FLAC-Datei."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        if warnings:
            warning = QLabel("Hinweise: " + " | ".join(warnings))
            warning.setWordWrap(True)
            layout.addWidget(warning)

        local = song_values(song)
        changed = merged.changed_fields(local)

        self.fields = [
            name
            for name in EDITABLE_FIELDS
            if name in changed
        ]

        self.table = QTableWidget(len(self.fields), 5)
        self.table.setHorizontalHeaderLabels(
            [
                "Übernehmen",
                "Feld",
                "Aktuell",
                "Vorschlag",
                "Quelle",
            ]
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        for row, name in enumerate(self.fields):
            checkbox = QTableWidgetItem()
            checkbox.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            checkbox.setCheckState(Qt.CheckState.Checked)

            self.table.setItem(row, 0, checkbox)
            self.table.setItem(
                row,
                1,
                QTableWidgetItem(FIELD_LABELS[name]),
            )
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(local.get(name, "")),
            )
            self.table.setItem(
                row,
                3,
                QTableWidgetItem(
                    merged.values.get(name, "")
                ),
            )
            self.table.setItem(
                row,
                4,
                QTableWidgetItem(
                    SOURCE_LABELS.get(
                        merged.sources.get(name, "local"),
                        "Lokal",
                    )
                ),
            )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        layout.addWidget(self.table)

        self.button_box = QDialogButtonBox()

        self.apply_button = QPushButton(
            "Auswahl in Editor übernehmen"
        )
        self.cancel_button = QPushButton("Abbrechen")

        self.button_box.addButton(
            self.apply_button,
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self.button_box.addButton(
            self.cancel_button,
            QDialogButtonBox.ButtonRole.RejectRole,
        )

        self.apply_button.clicked.connect(
            self._accept_selection
        )
        self.cancel_button.clicked.connect(self.reject)

        layout.addWidget(self.button_box)

    def _accept_selection(self):
        self.selected_fields = {
            name
            for row, name in enumerate(self.fields)
            if self.table.item(row, 0).checkState()
            == Qt.CheckState.Checked
        }

        if not self.selected_fields:
            return

        self.accept()
