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
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..batch_comparison_logic import (
    BatchSongProposal,
    CommonFieldComparison,
    build_common_field_comparisons,
    build_track_field_comparisons,
)
from ..models.metadata import FIELD_LABELS


SOURCE_LABELS = {
    "local": "Lokal",
    "apple_music": "Apple Music",
    "musicbrainz": "MusicBrainz",
}

SOURCE_ORDER = (
    "local",
    "apple_music",
    "musicbrainz",
)

PREFERRED_BACKGROUND = QColor(42, 78, 58)
SUPPLEMENT_BACKGROUND = QColor(50, 66, 86)
CONFLICT_BACKGROUND = QColor(92, 66, 38)


class BatchComparisonDialog(QDialog):
    def __init__(
        self,
        proposals: list[BatchSongProposal],
        *,
        primary_source: str,
        feature_handling: str,
        parent=None,
    ):
        super().__init__(parent)

        self.proposals = proposals
        self.primary_source = primary_source
        self.feature_handling = feature_handling
        self.selected_updates: dict[
            int,
            dict[str, str],
        ] = {}

        self.common_selectors: dict[
            str,
            QComboBox,
        ] = {}
        self.track_selectors: list[
            tuple[int, str, QComboBox, dict[str, str]]
        ] = []

        self.setWindowTitle(
            "Batch-Metadaten vergleichen"
        )
        self.resize(1380, 780)

        layout = QVBoxLayout(self)

        preferred_name = SOURCE_LABELS.get(
            primary_source,
            primary_source,
        )

        info = QLabel(
            f"{len(proposals)} Titel ausgewählt. "
            f"Bevorzugte Quelle: {preferred_name}. "
            "Gemeinsame Albumwerte und individuelle Trackwerte "
            "können getrennt geprüft werden. "
            "Die ausgewählten Werte werden nach der Bestätigung "
            "direkt in die FLAC-Dateien geschrieben."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        legend = QLabel(
            "Grün: bevorzugte Quelle · "
            "Blau: ergänzter Wert · "
            "Orange: Konflikt zwischen Quellen"
        )
        legend.setWordWrap(True)
        layout.addWidget(legend)

        warnings = [
            warning
            for proposal in proposals
            for warning in proposal.warnings
        ]

        if warnings:
            warning_label = QLabel(
                "Hinweise: "
                + " | ".join(dict.fromkeys(warnings))
            )
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)

        tabs = QTabWidget()
        tabs.addTab(
            self._create_common_tab(),
            "Gemeinsame Albumwerte",
        )
        tabs.addTab(
            self._create_track_tab(),
            "Individuelle Trackwerte",
        )
        layout.addWidget(tabs)

        buttons = QDialogButtonBox()

        self.save_button = QPushButton(
            "Ausgewählte Werte speichern"
        )
        cancel_button = QPushButton(
            "Abbrechen"
        )

        buttons.addButton(
            self.save_button,
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        buttons.addButton(
            cancel_button,
            QDialogButtonBox.ButtonRole.RejectRole,
        )

        self.save_button.clicked.connect(
            self._accept_selection
        )
        cancel_button.clicked.connect(
            self.reject
        )

        layout.addWidget(buttons)

    def _create_common_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        comparisons = (
            build_common_field_comparisons(
                self.proposals,
                primary_source=self.primary_source,
                feature_handling=self.feature_handling,
            )
        )
        self.common_comparisons = comparisons

        table = QTableWidget(
            len(comparisons),
            6,
        )
        table.setHorizontalHeaderLabels(
            [
                "Feld",
                "Lokal",
                "Apple Music",
                "MusicBrainz",
                "Auswahl",
                "Hinweis",
            ]
        )
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        table.setAlternatingRowColors(True)

        for row, comparison in enumerate(
            comparisons
        ):
            table.setItem(
                row,
                0,
                QTableWidgetItem(
                    FIELD_LABELS[
                        comparison.field_name
                    ]
                ),
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
                    source_name
                    == self.primary_source
                    and value
                    and value
                    != "<verschiedene Werte>"
                ):
                    item.setBackground(
                        PREFERRED_BACKGROUND
                    )

                table.setItem(
                    row,
                    column,
                    item,
                )

            selector = self._source_selector(
                comparison.values,
                comparison.default_source,
            )
            self.common_selectors[
                comparison.field_name
            ] = selector
            table.setCellWidget(
                row,
                4,
                selector,
            )

            status = self._status_text(
                comparison.has_conflict,
                comparison.is_supplemented,
                comparison.default_source,
            )
            status_item = QTableWidgetItem(
                status
            )
            self._style_status(
                status_item,
                comparison.has_conflict,
                comparison.is_supplemented,
            )
            table.setItem(
                row,
                5,
                status_item,
            )

        self._configure_table_header(table)
        self._highlight_header(
            table,
            self.primary_source,
        )

        layout.addWidget(table)
        return widget

    def _create_track_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        tree = QTreeWidget()
        tree.setColumnCount(6)
        tree.setHeaderLabels(
            [
                "Titel / Feld",
                "Lokal",
                "Apple Music",
                "MusicBrainz",
                "Auswahl",
                "Hinweis",
            ]
        )
        tree.setAlternatingRowColors(True)

        for proposal in self.proposals:
            parent = QTreeWidgetItem(
                [
                    (
                        f"{proposal.song.track or '?'} · "
                        f"{proposal.song.title}"
                    ),
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            parent_font = QFont(
                parent.font(0)
            )
            parent_font.setBold(True)
            parent.setFont(
                0,
                parent_font,
            )
            tree.addTopLevelItem(parent)

            comparisons = (
                build_track_field_comparisons(
                    proposal,
                    primary_source=(
                        self.primary_source
                    ),
                    feature_handling=(
                        self.feature_handling
                    ),
                )
            )

            for comparison in comparisons:
                child = QTreeWidgetItem(
                    [
                        FIELD_LABELS[
                            comparison.field_name
                        ],
                        comparison.values.get(
                            "local",
                            "",
                        ),
                        comparison.values.get(
                            "apple_music",
                            "",
                        ),
                        comparison.values.get(
                            "musicbrainz",
                            "",
                        ),
                        "",
                        self._status_text(
                            comparison.has_conflict,
                            comparison.is_supplemented,
                            comparison.default_source,
                        ),
                    ]
                )
                parent.addChild(child)

                selector = self._source_selector(
                    comparison.values,
                    comparison.default_source,
                )
                tree.setItemWidget(
                    child,
                    4,
                    selector,
                )
                self.track_selectors.append(
                    (
                        proposal.song_row,
                        comparison.field_name,
                        selector,
                        comparison.values,
                    )
                )

                if comparison.has_conflict:
                    child.setBackground(
                        5,
                        CONFLICT_BACKGROUND,
                    )
                elif comparison.is_supplemented:
                    child.setBackground(
                        5,
                        SUPPLEMENT_BACKGROUND,
                    )

                preferred_column = {
                    "local": 1,
                    "apple_music": 2,
                    "musicbrainz": 3,
                }.get(self.primary_source)

                if (
                    preferred_column is not None
                    and comparison.values.get(
                        self.primary_source,
                        "",
                    )
                ):
                    child.setBackground(
                        preferred_column,
                        PREFERRED_BACKGROUND,
                    )

            parent.setExpanded(True)

        header = tree.header()

        for column in (0, 4, 5):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        for column in (1, 2, 3):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch,
            )

        layout.addWidget(tree)
        return widget

    def _source_selector(
        self,
        values: dict[str, str],
        default_source: str,
    ) -> QComboBox:
        selector = QComboBox()

        for source_name in SOURCE_ORDER:
            value = values.get(
                source_name,
                "",
            )

            if (
                source_name != "local"
                and (
                    not value
                    or value
                    == "<verschiedene Werte>"
                )
            ):
                continue

            selector.addItem(
                SOURCE_LABELS[source_name],
                source_name,
            )

        default_index = selector.findData(
            default_source
        )

        if default_index >= 0:
            selector.setCurrentIndex(
                default_index
            )

        return selector

    def _accept_selection(self):
        updates: dict[int, dict[str, str]] = {
            proposal.song_row: {}
            for proposal in self.proposals
        }

        for comparison in self.common_comparisons:
            selector = self.common_selectors[
                comparison.field_name
            ]
            source_name = str(
                selector.currentData()
            )
            selected_value = (
                comparison.values.get(
                    source_name,
                    "",
                )
            )

            if (
                source_name == "local"
                or not selected_value
                or selected_value
                == "<verschiedene Werte>"
            ):
                continue

            for proposal in self.proposals:
                current_value = str(
                    getattr(
                        proposal.song,
                        comparison.field_name,
                        "",
                    )
                    or ""
                )

                if selected_value != current_value:
                    updates[
                        proposal.song_row
                    ][
                        comparison.field_name
                    ] = selected_value

        for (
            song_row,
            field_name,
            selector,
            values,
        ) in self.track_selectors:
            source_name = str(
                selector.currentData()
            )
            selected_value = values.get(
                source_name,
                "",
            )

            if source_name == "local":
                continue

            proposal = next(
                proposal
                for proposal in self.proposals
                if proposal.song_row == song_row
            )
            current_value = str(
                getattr(
                    proposal.song,
                    field_name,
                    "",
                )
                or ""
            )

            if (
                selected_value
                and selected_value
                != current_value
            ):
                updates[song_row][
                    field_name
                ] = selected_value

        self.selected_updates = {
            row: field_updates
            for row, field_updates in (
                updates.items()
            )
            if field_updates
        }

        if not self.selected_updates:
            return

        self.accept()

    @staticmethod
    def _status_text(
        has_conflict: bool,
        is_supplemented: bool,
        default_source: str,
    ) -> str:
        messages: list[str] = []

        if has_conflict:
            messages.append("Konflikt")

        if is_supplemented:
            messages.append("Ergänzt")

        if (
            default_source not in {
                "local",
            }
            and not has_conflict
            and not is_supplemented
        ):
            messages.append("Empfohlen")

        return ", ".join(messages)

    @staticmethod
    def _style_status(
        item: QTableWidgetItem,
        has_conflict: bool,
        is_supplemented: bool,
    ):
        if has_conflict:
            item.setBackground(
                CONFLICT_BACKGROUND
            )
        elif is_supplemented:
            item.setBackground(
                SUPPLEMENT_BACKGROUND
            )

    @staticmethod
    def _configure_table_header(
        table: QTableWidget,
    ):
        header = table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        for column in (1, 2, 3):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch,
            )

        for column in (4, 5):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

    @staticmethod
    def _highlight_header(
        table: QTableWidget,
        primary_source: str,
    ):
        column = {
            "local": 1,
            "apple_music": 2,
            "musicbrainz": 3,
        }.get(primary_source)

        if column is None:
            return

        item = table.horizontalHeaderItem(
            column
        )

        if item is None:
            return

        font = QFont(item.font())
        font.setBold(True)
        item.setFont(font)
        item.setToolTip(
            "Bevorzugte Metadatenquelle"
        )
