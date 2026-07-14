from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..comparison_logic import (
    SOURCE_ORDER,
    FieldComparison,
    build_field_comparisons,
)
from ..models.metadata import (
    FIELD_LABELS,
    MetadataCandidate,
)
from ..models.song import Song


SOURCE_LABELS = {
    "local": "Lokal",
    "apple_music": "Apple Music",
    "musicbrainz": "MusicBrainz",
}

PREFERRED_BACKGROUND = QColor(42, 78, 58)
SUPPLEMENT_BACKGROUND = QColor(50, 66, 86)
CONFLICT_BACKGROUND = QColor(92, 66, 38)


class ComparisonDialog(QDialog):
    def __init__(
        self,
        song: Song,
        candidates: list[MetadataCandidate],
        *,
        primary_source: str,
        feature_handling: str,
        warnings: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.song = song
        self.candidates = candidates
        self.primary_source = primary_source
        self.feature_handling = feature_handling

        self.selected_fields: set[str] = set()
        self.selected_values: dict[str, str] = {}

        self.comparisons = build_field_comparisons(
            song,
            candidates,
            primary_source=primary_source,
            feature_handling=feature_handling,
        )
        self.source_selectors: dict[
            str,
            QComboBox,
        ] = {}

        self.setWindowTitle("Metadaten vergleichen")
        self.resize(1260, 680)

        layout = QVBoxLayout(self)

        preferred_name = SOURCE_LABELS.get(
            primary_source,
            primary_source,
        )

        info = QLabel(
            f"Bevorzugte Quelle: {preferred_name}. "
            "Du kannst für jedes Feld einzeln zwischen den vorhandenen "
            "Werten wählen. Erst der spätere Klick auf "
            "„Änderungen speichern“ schreibt in die FLAC-Datei."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        legend = QLabel(
            "Blau: durch eine andere Quelle ergänzt · "
            "Orange: Anbieter liefern unterschiedliche Werte"
        )
        legend.setWordWrap(True)
        layout.addWidget(legend)

        if warnings:
            warning = QLabel(
                "Hinweise: "
                + " | ".join(warnings)
            )
            warning.setWordWrap(True)
            layout.addWidget(warning)

        self.table = QTableWidget(
            len(self.comparisons),
            6,
        )
        self.table.setHorizontalHeaderLabels(
            [
                "Feld",
                "Lokal",
                "Apple Music",
                "MusicBrainz",
                "Auswahl",
                "Hinweis",
            ]
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)

        for row, comparison in enumerate(
            self.comparisons
        ):
            self._populate_row(
                row,
                comparison,
            )

        self._highlight_preferred_column()

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        for column in (1, 2, 3):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch,
            )

        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        layout.addWidget(self.table)

        self.button_box = QDialogButtonBox()

        self.apply_button = QPushButton(
            "Auswahl in Editor übernehmen"
        )
        self.cancel_button = QPushButton(
            "Abbrechen"
        )

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
        self.cancel_button.clicked.connect(
            self.reject
        )

        layout.addWidget(self.button_box)

    def _populate_row(
        self,
        row: int,
        comparison: FieldComparison,
    ):
        field_item = QTableWidgetItem(
            FIELD_LABELS[comparison.field_name]
        )
        self.table.setItem(
            row,
            0,
            field_item,
        )

        for column, source_name in enumerate(
            SOURCE_ORDER,
            start=1,
        ):
            value = comparison.values.get(
                source_name,
                "",
            )
            item = QTableWidgetItem(value)

            if (
                source_name == self.primary_source
                and value
            ):
                item.setBackground(
                    PREFERRED_BACKGROUND
                )

            self.table.setItem(
                row,
                column,
                item,
            )

        selector = QComboBox()

        for source_name in SOURCE_ORDER:
            value = comparison.values.get(
                source_name,
                "",
            )

            if not value and source_name != "local":
                continue

            selector.addItem(
                SOURCE_LABELS[source_name],
                source_name,
            )

        default_index = selector.findData(
            comparison.default_source
        )

        if default_index >= 0:
            selector.setCurrentIndex(
                default_index
            )

        selector.currentIndexChanged.connect(
            lambda _index,
            field_name=comparison.field_name:
            self._update_row_status(field_name)
        )

        self.source_selectors[
            comparison.field_name
        ] = selector

        self.table.setCellWidget(
            row,
            4,
            selector,
        )

        status_item = QTableWidgetItem()
        self.table.setItem(
            row,
            5,
            status_item,
        )

        self._update_row_status(
            comparison.field_name
        )

    def _update_row_status(
        self,
        field_name: str,
    ):
        row = next(
            index
            for index, comparison
            in enumerate(self.comparisons)
            if comparison.field_name == field_name
        )
        comparison = self.comparisons[row]
        selector = self.source_selectors[
            field_name
        ]
        selected_source = str(
            selector.currentData()
        )

        messages: list[str] = []

        if comparison.has_conflict:
            messages.append("Konflikt")

        if (
            selected_source != self.primary_source
            and selected_source != "local"
            and not comparison.values.get(
                self.primary_source,
                "",
            )
        ):
            messages.append("Ergänzt")

        if selected_source == self.primary_source:
            messages.append("Bevorzugt")

        status_item = self.table.item(
            row,
            5,
        )
        status_item.setText(
            ", ".join(messages)
        )

        if comparison.has_conflict:
            status_item.setBackground(
                CONFLICT_BACKGROUND
            )
        elif "Ergänzt" in messages:
            status_item.setBackground(
                SUPPLEMENT_BACKGROUND
            )

    def _highlight_preferred_column(self):
        source_to_column = {
            "local": 1,
            "apple_music": 2,
            "musicbrainz": 3,
        }
        column = source_to_column.get(
            self.primary_source
        )

        if column is None:
            return

        header_item = self.table.horizontalHeaderItem(
            column
        )

        if header_item is None:
            return

        font = QFont(header_item.font())
        font.setBold(True)
        header_item.setFont(font)
        header_item.setToolTip(
            "Bevorzugte Metadatenquelle"
        )

    def _accept_selection(self):
        selected_values: dict[str, str] = {}
        selected_fields: set[str] = set()

        for comparison in self.comparisons:
            selector = self.source_selectors[
                comparison.field_name
            ]
            source_name = str(
                selector.currentData()
            )
            value = comparison.values.get(
                source_name,
                "",
            )

            local_value = comparison.values.get(
                "local",
                "",
            )

            if (
                source_name != "local"
                and value != local_value
            ):
                selected_fields.add(
                    comparison.field_name
                )
                selected_values[
                    comparison.field_name
                ] = value

        if not selected_fields:
            return

        self.selected_fields = selected_fields
        self.selected_values = selected_values
        self.accept()
