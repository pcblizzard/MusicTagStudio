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

from .providers.apple_music import AppleMusicResult


class AppleMusicResultsDialog(QDialog):
    def __init__(
        self,
        results: list[AppleMusicResult],
        parent=None,
    ):
        super().__init__(parent)

        self.results = results
        self.selected_result: AppleMusicResult | None = None

        self.setWindowTitle("Apple-Music-Vorschläge")
        self.resize(1100, 520)

        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Feature-Nennungen wie „[feat. …]“, „(feat. …)“ oder "
            "„feat. …“ werden bereits aus dem Titel entfernt und nach "
            "deinen Regeln zum Künstlerfeld hinzugefügt. "
            "Die Werte werden nur in den Editor übernommen und erst nach "
            "„Änderungen speichern“ in die FLAC-Datei geschrieben."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.table = QTableWidget(len(results), 10)
        self.table.setHorizontalHeaderLabels(
            [
                "Treffer",
                "Titel",
                "Künstler",
                "Album",
                "Track",
                "Disc",
                "Jahr",
                "Genre",
                "Dauer",
                "Apple-ID",
            ]
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.doubleClicked.connect(
            self.accept_selected_result
        )

        for row, result in enumerate(results):
            track_text = result.track

            if result.total_tracks:
                track_text = (
                    f"{result.track}/{result.total_tracks}"
                )

            disc_text = result.disc

            if result.total_discs:
                disc_text = (
                    f"{result.disc}/{result.total_discs}"
                )

            values = [
                f"{result.score} %",
                result.title,
                result.artist,
                result.album,
                track_text,
                disc_text,
                result.year,
                result.genre,
                result.duration_text,
                str(result.track_id or ""),
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)

                if column in (0, 4, 5, 6, 8):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )

                self.table.setItem(row, column, item)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        for column in range(4, 10):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        layout.addWidget(self.table)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )

        apply_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Apply
        )
        cancel_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        )

        if apply_button is not None:
            apply_button.setText("Vorschlag übernehmen")

        if cancel_button is not None:
            cancel_button.setText("Abbrechen")

        self.button_box.accepted.connect(
            self.accept_selected_result
        )
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        if results:
            self.table.selectRow(0)
            self.table.setCurrentCell(0, 0)

    def accept_selected_result(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.results):
            return

        self.selected_result = self.results[row]
        self.accept()
