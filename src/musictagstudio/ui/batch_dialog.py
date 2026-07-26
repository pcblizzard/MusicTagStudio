from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
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
    build_common_field_comparisons,
    build_track_field_comparisons,
)
from ..comparison_logic import (
    SOURCE_LABELS,
    SOURCE_ORDER,
)
from ..direct_album_lookup import (
    DirectAlbumLookupError,
    build_album_matching_result,
    lookup_apple_album_by_id,
)
from ..direct_references import (
    DirectAlbumReferenceError,
    parse_album_reference,
)
from ..i18n import tr
from ..settings import load_settings


# SOURCE_LABELS und SOURCE_ORDER kommen zentral aus comparison_logic, damit
# eine neue Quelle nur an einer Stelle ergänzt werden muss. Spaltenlayout:
# 0 = Feld, danach je eine Wertspalte pro Quelle, dann Auswahl und Hinweis.
_SELECTOR_COLUMN = len(SOURCE_ORDER) + 1
_STATUS_COLUMN = len(SOURCE_ORDER) + 2
_COLUMN_COUNT = len(SOURCE_ORDER) + 3


def _header_labels(language: str = "automatic") -> list[str]:
    return (
        [tr("col_field", language)]
        + [SOURCE_LABELS[source] for source in SOURCE_ORDER]
        + [tr("col_selection", language), tr("col_hint", language)]
    )


PREFERRED_BACKGROUND = QColor(42, 78, 58)
SUPPLEMENT_BACKGROUND = QColor(50, 66, 86)
CONFLICT_BACKGROUND = QColor(92, 66, 38)


def apple_link_hint_needed(
    proposals: list[BatchSongProposal],
) -> bool:
    """
    Erkennt, ob Apple Music das Album nicht sicher zuordnen konnte.

    In diesem Fall lässt sich die korrekte Trackliste zuverlässig über
    „Direkt-Album" mit dem Apple-Music-Link laden.
    """
    for proposal in proposals:
        for warning in proposal.warnings:
            if "Apple" in warning and (
                "sicher" in warning
                or "Albumtrackliste" in warning
            ):
                return True

    return False


class _AppleAlbumSignals(QObject):
    finished = Signal(str, object)
    failed = Signal(str)


class _AppleAlbumTask(QRunnable):
    def __init__(self, reference_text: str, country: str, language: str = "automatic"):
        super().__init__()
        self.signals = _AppleAlbumSignals()
        self._text = reference_text
        self._country = country
        self._language = language

    @Slot()
    def run(self):
        try:
            reference = parse_album_reference(self._text)
        except DirectAlbumReferenceError as error:
            self.signals.failed.emit(str(error))
            return

        if reference.provider != "apple_music":
            self.signals.failed.emit(
                tr("apple_link_provider", self._language)
            )
            return

        try:
            result = lookup_apple_album_by_id(
                reference.reference_id,
                country=self._country,
            )
        except DirectAlbumLookupError as error:
            self.signals.failed.emit(str(error))
            return

        self.signals.finished.emit(reference.reference_id, result)


class BatchComparisonDialog(QDialog):
    def __init__(
        self,
        proposals: list[BatchSongProposal],
        *,
        primary_source: str,
        feature_handling: str,
        parent=None,
        language: str = "automatic",
    ):
        super().__init__(parent)

        self.language = language
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
            tr("batch_compare_title", language)
        )
        self.resize(1380, 780)

        layout = QVBoxLayout(self)

        preferred_name = SOURCE_LABELS.get(
            primary_source,
            primary_source,
        )

        info = QLabel(
            tr(
                "batch_info",
                language,
                count=len(proposals),
                source=preferred_name,
            )
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        legend = QLabel(
            tr("batch_legend", language)
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
                tr(
                    "comp_warnings",
                    language,
                    warnings=" | ".join(dict.fromkeys(warnings)),
                )
            )
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)

        self._apple_pool = QThreadPool(self)
        self._apple_pool.setMaxThreadCount(1)
        self._create_apple_link_row(layout)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._populate_tabs()

        buttons = QDialogButtonBox()

        self.save_button = QPushButton(
            tr("save_selected_values", language)
        )
        cancel_button = QPushButton(
            tr("cancel", language)
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

    def _apple_link_offer_needed(self) -> bool:
        """
        Entscheidet, ob das Feld für den Apple-Link angeboten wird.

        Es erscheint bei einer Apple-bezogenen Warnung oder immer dann,
        wenn Apple Music bevorzugte Quelle ist, aber überhaupt keinen
        Treffer geliefert hat (leere Apple-Spalte).
        """
        if apple_link_hint_needed(self.proposals):
            return True

        if self.primary_source != "apple_music":
            return False

        has_apple = any(
            candidate.source == "apple_music"
            for proposal in self.proposals
            for candidate in proposal.candidates
        )
        return not has_apple

    def _create_apple_link_row(self, layout: QVBoxLayout) -> None:
        if not self._apple_link_offer_needed():
            return

        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(0, 0, 0, 0)

        hint = QLabel(tr("apple_link_hint", self.language))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #f0b060; font-weight: bold;")
        box.addWidget(hint)

        row = QHBoxLayout()
        self._apple_link_edit = QLineEdit()
        self._apple_link_edit.setPlaceholderText(
            "https://music.apple.com/…/album/…/1234567890"
        )
        self._apple_link_edit.returnPressed.connect(
            self._load_apple_album_from_link
        )
        self._apple_link_button = QPushButton(tr("apple_link_load", self.language))
        self._apple_link_button.clicked.connect(
            self._load_apple_album_from_link
        )
        row.addWidget(self._apple_link_edit, 1)
        row.addWidget(self._apple_link_button)
        box.addLayout(row)

        self._apple_link_status = QLabel("")
        self._apple_link_status.setWordWrap(True)
        box.addWidget(self._apple_link_status)

        layout.addWidget(container)

    def _populate_tabs(self) -> None:
        self.common_selectors = {}
        self.track_selectors = []

        while self.tabs.count():
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            widget.deleteLater()

        self.tabs.addTab(
            self._create_common_tab(),
            tr("tab_common_album", self.language),
        )
        self.tabs.addTab(
            self._create_track_tab(),
            tr("tab_individual_track", self.language),
        )

    def _load_apple_album_from_link(self) -> None:
        text = self._apple_link_edit.text().strip()

        if not text:
            self._apple_link_status.setText(
                tr("apple_link_required", self.language)
            )
            return

        self._apple_link_button.setEnabled(False)
        self._apple_link_status.setText(tr("apple_album_loading", self.language))

        settings = load_settings()
        task = _AppleAlbumTask(text, settings.apple_country, self.language)
        task.signals.finished.connect(self._on_apple_album_loaded)
        task.signals.failed.connect(self._on_apple_album_failed)
        self._apple_pool.start(task)

    @Slot(str, object)
    def _on_apple_album_loaded(
        self,
        collection_id: str,
        album_result: object,
    ) -> None:
        songs = [proposal.song for proposal in self.proposals]
        matching = build_album_matching_result(songs, album_result)

        injected = 0
        for match in matching.matches:
            if match.confidence == "Mehrdeutig" and match.score < 80:
                continue

            proposal = self.proposals[match.local_index]
            candidate = replace(
                match.track.as_candidate("apple_music"),
                confidence=min(100, max(0, match.score)),
                release_id=collection_id,
            )
            proposal.candidates[:] = [
                existing
                for existing in proposal.candidates
                if existing.source != "apple_music"
            ]
            proposal.candidates.append(candidate)
            injected += 1

        self._populate_tabs()
        self._apple_link_button.setEnabled(True)
        self._apple_link_status.setText(
            tr(
                "apple_album_loaded",
                self.language,
                injected=injected,
                total=len(self.proposals),
            )
        )

    @Slot(str)
    def _on_apple_album_failed(self, message: str) -> None:
        self._apple_link_button.setEnabled(True)
        self._apple_link_status.setText(
            tr("apple_album_failed", self.language, message=message)
        )

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
            _COLUMN_COUNT,
        )
        table.setHorizontalHeaderLabels(
            _header_labels(self.language)
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
                    tr(f"field_{comparison.field_name}", self.language)
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
                display_value = (
                    comparison.display_values.get(
                        source_name,
                        value,
                    )
                )
                item = QTableWidgetItem(
                    display_value
                )

                if (
                    value
                    == "<verschiedene Werte>"
                    and display_value
                ):
                    item.setToolTip(
                        tr(
                            "different_values_tip",
                            self.language,
                            values=display_value,
                        )
                    )

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
                _SELECTOR_COLUMN,
                selector,
            )

            status = self._status_text(
                comparison.has_conflict,
                comparison.is_supplemented,
                comparison.default_source,
                self.language,
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
                _STATUS_COLUMN,
                status_item,
            )

        self._configure_table_header(table)
        self._highlight_header(
            table,
            self.primary_source,
            self.language,
        )

        layout.addWidget(table)
        return widget

    def _create_track_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        tree = QTreeWidget()
        tree.setColumnCount(_COLUMN_COUNT)
        tree.setHeaderLabels(
            [tr("col_track_field", self.language)]
            + [SOURCE_LABELS[source] for source in SOURCE_ORDER]
            + [tr("col_selection", self.language), tr("col_hint", self.language)]
        )
        tree.setAlternatingRowColors(True)

        for proposal in self.proposals:
            parent = QTreeWidgetItem(
                [
                    (
                        f"{proposal.song.track or '?'} · "
                        f"{proposal.song.title}"
                    )
                ]
                + [""] * (_COLUMN_COUNT - 1)
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
                        tr(f"field_{comparison.field_name}", self.language)
                    ]
                    + [
                        comparison.values.get(source, "")
                        for source in SOURCE_ORDER
                    ]
                    + [
                        "",
                        self._status_text(
                            comparison.has_conflict,
                            comparison.is_supplemented,
                            comparison.default_source,
                            self.language,
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
                    _SELECTOR_COLUMN,
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
                        _STATUS_COLUMN,
                        CONFLICT_BACKGROUND,
                    )
                elif comparison.is_supplemented:
                    child.setBackground(
                        _STATUS_COLUMN,
                        SUPPLEMENT_BACKGROUND,
                    )

                preferred_column = {
                    source: index + 1
                    for index, source in enumerate(SOURCE_ORDER)
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

        for column in (0, _SELECTOR_COLUMN, _STATUS_COLUMN):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        for column in range(1, len(SOURCE_ORDER) + 1):
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
            QMessageBox.information(
                self,
                tr("no_changes_title", self.language),
                tr("no_changes_msg", self.language),
            )
            return

        self.accept()

    @staticmethod
    def _status_text(
        has_conflict: bool,
        is_supplemented: bool,
        default_source: str,
        language: str = "automatic",
    ) -> str:
        messages: list[str] = []

        if has_conflict:
            messages.append(tr("comp_conflict", language))

        if is_supplemented:
            messages.append(tr("comp_supplemented", language))

        if (
            default_source not in {
                "local",
            }
            and not has_conflict
            and not is_supplemented
        ):
            messages.append(tr("comp_recommended", language))

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

        for column in range(1, len(SOURCE_ORDER) + 1):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.Stretch,
            )

        for column in (_SELECTOR_COLUMN, _STATUS_COLUMN):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

    @staticmethod
    def _highlight_header(
        table: QTableWidget,
        primary_source: str,
        language: str = "automatic",
    ):
        column = {
            source: index + 1
            for index, source in enumerate(SOURCE_ORDER)
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
            tr("preferred_source_tip", language)
        )
