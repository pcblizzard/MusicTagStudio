from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..cover_source_catalog import COVER_SOURCES
from ..provider_catalog import PROVIDERS
from ..library_sources import MusicSource, new_source
from ..settings import AppSettings
from ..i18n import SUPPORTED_LANGUAGES, tr


STATUS_STYLES = {
    "supported": (
        "color:#2e9d50;font-weight:600;"
    ),
    "setup_required": (
        "color:#c28b00;font-weight:600;"
    ),
    "unsupported": (
        "color:#d04a4a;font-weight:600;"
    ),
}


class SettingsDialog(QDialog):
    settings_saved = Signal(object)

    def __init__(
        self,
        settings: AppSettings,
        parent=None,
        *,
        embedded: bool = False,
    ):
        super().__init__(parent)

        self.embedded = embedded
        self.initial_settings = settings
        self.provider_buttons = {}
        self.cover_buttons = {}

        if not self.embedded:
            self.setWindowTitle("Einstellungen")
            self.resize(740, 860)

        outer_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        content = QWidget()
        layout = QVBoxLayout(content)

        appearance = QGroupBox("Darstellung")
        appearance_form = QFormLayout(
            appearance
        )

        self.theme_combo = QComboBox()

        for label, data in (
            (
                "Automatisch (Windows-Einstellung)",
                "automatic",
            ),
            ("Hell", "light"),
            ("Dunkel", "dark"),
        ):
            self.theme_combo.addItem(
                label,
                data,
            )

        self._set_combo_value(
            self.theme_combo,
            settings.theme,
        )
        appearance_form.addRow(
            "Theme:",
            self.theme_combo,
        )

        self.language_combo = QComboBox()
        for code, label in SUPPORTED_LANGUAGES:
            self.language_combo.addItem(
                label,
                code,
            )
        self._set_combo_value(
            self.language_combo,
            settings.language,
        )
        appearance_form.addRow(
            "Sprache:",
            self.language_combo,
        )
        layout.addWidget(appearance)

        library = QGroupBox(
            "Musikquellen"
        )
        library_layout = QVBoxLayout(
            library
        )
        library_info = QLabel(
            "Mehrere lokale Laufwerke, externe Festplatten und "
            "Netzwerkpfade können gemeinsam indiziert werden. "
            "Nicht erreichbare Quellen bleiben im Index sichtbar."
        )
        library_info.setWordWrap(
            True
        )
        library_layout.addWidget(
            library_info
        )

        self.source_table = QTableWidget(
            0,
            4,
        )
        self.source_table.setHorizontalHeaderLabels(
            [
                "Aktiv",
                "Name",
                "Pfad",
                "Status",
            ]
        )
        self.source_table.horizontalHeader().setStretchLastSection(
            True
        )
        library_layout.addWidget(
            self.source_table
        )

        source_buttons = QHBoxLayout()
        self.add_source_button = QPushButton(
            "Quelle hinzufügen"
        )
        self.add_source_button.clicked.connect(
            self._add_source
        )
        self.remove_source_button = QPushButton(
            "Quelle entfernen"
        )
        self.remove_source_button.clicked.connect(
            self._remove_source
        )
        source_buttons.addWidget(
            self.add_source_button
        )
        source_buttons.addWidget(
            self.remove_source_button
        )
        source_buttons.addStretch()
        library_layout.addLayout(
            source_buttons
        )

        self.load_sources_checkbox = QCheckBox(
            "Hinterlegte Quellen beim Programmstart automatisch laden"
        )
        self.load_sources_checkbox.setChecked(
            settings.load_sources_on_startup
        )
        library_layout.addWidget(
            self.load_sources_checkbox
        )

        self.scan_sources_checkbox = QCheckBox(
            "Beim Programmstart nach neuen oder geänderten Audiodateien suchen"
        )
        self.scan_sources_checkbox.setChecked(
            settings.scan_sources_on_startup
        )
        library_layout.addWidget(
            self.scan_sources_checkbox
        )

        self._populate_sources(
            settings.music_sources
        )
        layout.addWidget(
            library
        )

        providers = QGroupBox(
            "Metadatenquelle"
        )
        provider_layout = QVBoxLayout(
            providers
        )
        provider_info = QLabel(
            "Die ausgewählte Quelle besitzt Priorität. "
            "Andere unterstützte Quellen können nur fehlende "
            "Felder ergänzen."
        )
        provider_info.setWordWrap(True)
        provider_layout.addWidget(
            provider_info
        )

        self.provider_group = QButtonGroup(
            self
        )
        self.provider_group.setExclusive(
            True
        )

        for item in PROVIDERS:
            self._provider_row(
                provider_layout,
                self.provider_group,
                self.provider_buttons,
                item.provider_id,
                item.name,
                item.status,
                item.status_text,
                item.tooltip,
                item.selectable,
            )

        self.provider_buttons.get(
            settings.selected_provider,
            self.provider_buttons[
                "apple_music"
            ],
        ).setChecked(True)

        self.enrich_checkbox = QCheckBox(
            "Fehlende Felder durch andere "
            "unterstützte Quellen ergänzen"
        )
        self.enrich_checkbox.setChecked(
            settings.enrich_missing_fields
        )
        provider_layout.addWidget(
            self.enrich_checkbox
        )

        self.country_combo = QComboBox()

        for code, name in (
            ("DE", "Deutschland"),
            ("AT", "Österreich"),
            ("CH", "Schweiz"),
            ("US", "USA"),
            ("GB", "Großbritannien"),
        ):
            self.country_combo.addItem(
                f"{name} ({code})",
                code,
            )

        self._set_combo_value(
            self.country_combo,
            settings.apple_country,
        )
        country_form = QFormLayout()
        country_form.addRow(
            "Apple-Store:",
            self.country_combo,
        )
        provider_layout.addLayout(
            country_form
        )
        layout.addWidget(providers)

        covers = QGroupBox("Coverquellen")
        cover_layout = QVBoxLayout(covers)
        cover_info = QLabel(
            "Metadaten- und Coverquelle sind unabhängig. "
            "Rot bedeutet, dass die Quelle in MusicTagStudio "
            "aktuell nicht nutzbar ist."
        )
        cover_info.setWordWrap(True)
        cover_layout.addWidget(
            cover_info
        )

        self.cover_group = QButtonGroup(
            self
        )
        self.cover_group.setExclusive(
            True
        )

        for item in COVER_SOURCES:
            self._provider_row(
                cover_layout,
                self.cover_group,
                self.cover_buttons,
                item.source_id,
                item.name,
                item.status,
                item.status_text,
                item.tooltip,
                item.selectable,
            )

        self.cover_buttons.get(
            settings.selected_cover_source,
            self.cover_buttons[
                "apple_music"
            ],
        ).setChecked(True)

        self.cover_fallback_checkbox = (
            QCheckBox(
                "Andere unterstützte Quelle verwenden, "
                "wenn kein geeignetes Cover gefunden wird"
            )
        )
        self.cover_fallback_checkbox.setChecked(
            settings.cover_fallback_enabled
        )
        cover_layout.addWidget(
            self.cover_fallback_checkbox
        )

        cover_form = QFormLayout()

        self.minimum_cover_size_spin = (
            QSpinBox()
        )
        self.minimum_cover_size_spin.setRange(
            100,
            10000,
        )
        self.minimum_cover_size_spin.setValue(
            settings.minimum_cover_size
        )
        self.minimum_cover_size_spin.setSuffix(
            " px"
        )
        cover_form.addRow(
            "Mindestauflösung:",
            self.minimum_cover_size_spin,
        )

        self.artist_levels_spin = QSpinBox()
        self.artist_levels_spin.setRange(
            1,
            5,
        )
        self.artist_levels_spin.setValue(
            settings.artist_folder_levels_up
        )
        self.artist_levels_spin.setToolTip(
            "Anzahl der Ordnerebenen, die vom Albumordner "
            "zum Zielordner des 400-px-Covers nach oben "
            "gegangen wird."
        )
        cover_form.addRow(
            "Künstlerordner liegt:",
            self.artist_levels_spin,
        )

        cover_layout.addLayout(
            cover_form
        )
        layout.addWidget(covers)

        audio_analysis = QGroupBox(
            "Audioanalyse"
        )
        audio_form = QFormLayout(
            audio_analysis
        )

        self.parallel_jobs_combo = QComboBox()
        self.parallel_jobs_combo.addItem(
            "Automatisch",
            0,
        )

        for count in (
            2,
            4,
            6,
            8,
        ):
            self.parallel_jobs_combo.addItem(
                str(count),
                count,
            )

        self._set_combo_value(
            self.parallel_jobs_combo,
            settings.audio_analysis_parallel_jobs,
        )
        self.parallel_jobs_combo.setToolTip(
            "Automatisch verwendet auf typischen Systemen bis "
            "zu vier parallele FFmpeg-Prozesse. Eine höhere Zahl "
            "kann die Analyse beschleunigen, belastet den Rechner "
            "aber stärker."
        )
        audio_form.addRow(
            "Parallele Analysen:",
            self.parallel_jobs_combo,
        )
        layout.addWidget(
            audio_analysis
        )

        online_catalogs = QGroupBox(
            "Online-Kataloge"
        )
        online_catalogs_form = QFormLayout(
            online_catalogs
        )
        self.discogs_token_edit = QLineEdit(
            settings.discogs_token
        )
        self.discogs_token_edit.setEchoMode(
            QLineEdit.EchoMode.Password
        )
        self.discogs_token_edit.setPlaceholderText(
            "Persönliches Discogs-Token"
        )
        self.discogs_token_edit.setToolTip(
            "Das Token wird nur lokal in config.toml gespeichert und "
            "für Anfragen an api.discogs.com verwendet."
        )
        online_catalogs_form.addRow(
            "Discogs-Token:",
            self.discogs_token_edit,
        )
        discogs_info = QLabel(
            "Ohne Token verwendet die Medienbibliothek ausschließlich "
            "MusicBrainz. Mit Token ergänzt Discogs Labels, Formate, "
            "Cover und fehlende Veröffentlichungen."
        )
        discogs_info.setWordWrap(True)
        online_catalogs_form.addRow(discogs_info)
        layout.addWidget(online_catalogs)

        normalization = QGroupBox(
            "Normalisierung"
        )
        normalization_form = QFormLayout(
            normalization
        )

        self.feature_combo = QComboBox()

        for label, data in (
            (
                "Gast nur im Künstlerfeld",
                "artist_only",
            ),
            (
                "Gast im Titel und Künstlerfeld",
                "title_and_artist",
            ),
            (
                "Schreibweise der Quelle beibehalten",
                "source",
            ),
        ):
            self.feature_combo.addItem(
                label,
                data,
            )

        self._set_combo_value(
            self.feature_combo,
            settings.feature_handling,
        )
        normalization_form.addRow(
            "Feature-Künstler:",
            self.feature_combo,
        )
        layout.addWidget(
            normalization
        )

        layout.addStretch()

        scroll_area.setWidget(content)
        outer_layout.addWidget(
            scroll_area
        )

        if self.embedded:
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save
            )
            button_box.accepted.connect(
                self._save_embedded
            )
        else:
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save
                | QDialogButtonBox.StandardButton.Cancel
            )
            button_box.accepted.connect(
                self.accept
            )
            button_box.rejected.connect(
                self.reject
            )
        self.button_box = button_box
        self._update_button_texts()
        self.language_combo.currentIndexChanged.connect(
            self._update_button_texts
        )
        outer_layout.addWidget(
            button_box
        )

    def _update_button_texts(
        self,
        _index: int = -1,
    ) -> None:
        language = str(
            self.language_combo.currentData()
            or "automatic"
        )
        save_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Save
        )
        if save_button is not None:
            save_button.setText(
                tr("save", language)
            )
        cancel_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        )
        if cancel_button is not None:
            cancel_button.setText(
                tr("cancel", language)
            )

    def _populate_sources(
        self,
        sources: tuple[MusicSource, ...],
    ) -> None:
        self.source_table.setRowCount(
            0
        )

        for source in sources:
            self._append_source_row(
                source
            )

    def _append_source_row(
        self,
        source: MusicSource,
    ) -> None:
        row = self.source_table.rowCount()
        self.source_table.insertRow(
            row
        )

        active = QTableWidgetItem()
        active.setFlags(
            active.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        active.setCheckState(
            (
                Qt.CheckState.Checked
                if source.enabled
                else Qt.CheckState.Unchecked
            )
        )
        active.setData(
            Qt.ItemDataRole.UserRole,
            source.source_id,
        )
        self.source_table.setItem(
            row,
            0,
            active,
        )
        self.source_table.setItem(
            row,
            1,
            QTableWidgetItem(
                source.name
            ),
        )
        self.source_table.setItem(
            row,
            2,
            QTableWidgetItem(
                source.path
            ),
        )
        status = (
            "Erreichbar"
            if Path(
                source.path
            ).is_dir()
            else "Pfad nicht gefunden"
        )
        status_item = QTableWidgetItem(
            status
        )
        status_item.setFlags(
            status_item.flags()
            & ~Qt.ItemFlag.ItemIsEditable
        )
        self.source_table.setItem(
            row,
            3,
            status_item,
        )

    def _add_source(
        self,
    ) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Musikquelle auswählen",
            "",
        )

        if not folder:
            return

        self._append_source_row(
            new_source(
                folder
            )
        )

    def _remove_source(
        self,
    ) -> None:
        row = self.source_table.currentRow()

        if row >= 0:
            self.source_table.removeRow(
                row
            )

    def _selected_sources(
        self,
    ) -> tuple[MusicSource, ...]:
        sources: list[MusicSource] = []

        for row in range(
            self.source_table.rowCount()
        ):
            active = self.source_table.item(
                row,
                0,
            )
            name_item = self.source_table.item(
                row,
                1,
            )
            path_item = self.source_table.item(
                row,
                2,
            )

            if (
                active is None
                or name_item is None
                or path_item is None
            ):
                continue

            path_value = path_item.text().strip()

            if not path_value:
                continue

            source_id = str(
                active.data(
                    Qt.ItemDataRole.UserRole
                )
                or ""
            ).strip()

            if not source_id:
                source_id = new_source(
                    path_value
                ).source_id

            sources.append(
                MusicSource(
                    source_id=source_id,
                    name=name_item.text().strip()
                    or Path(
                        path_value
                    ).name
                    or path_value,
                    path=path_value,
                    enabled=(
                        active.checkState()
                        == Qt.CheckState.Checked
                    ),
                )
            )

        return tuple(
            sources
        )

    def _save_embedded(
        self,
    ) -> None:
        new_settings = self.selected_settings()
        self.initial_settings = new_settings
        self.settings_saved.emit(
            new_settings
        )

    def _provider_row(
        self,
        layout,
        group,
        storage,
        item_id,
        name,
        status,
        status_text,
        tooltip,
        selectable,
    ):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(
            4,
            3,
            4,
            3,
        )

        button = QRadioButton(name)
        button.setEnabled(selectable)
        button.setToolTip(tooltip)

        status_label = QLabel(
            status_text
        )
        status_label.setStyleSheet(
            STATUS_STYLES[status]
        )
        status_label.setToolTip(
            tooltip
        )
        row.setToolTip(tooltip)

        group.addButton(button)
        storage[item_id] = button

        row_layout.addWidget(button)
        row_layout.addStretch()
        row_layout.addWidget(
            status_label
        )
        layout.addWidget(row)

    def selected_settings(
        self,
    ) -> AppSettings:
        provider = next(
            (
                item_id
                for item_id, button
                in self.provider_buttons.items()
                if button.isChecked()
            ),
            "apple_music",
        )
        cover = next(
            (
                item_id
                for item_id, button
                in self.cover_buttons.items()
                if button.isChecked()
            ),
            "apple_music",
        )

        return replace(
            self.initial_settings,
            theme=str(
                self.theme_combo.currentData()
            ),
            language=str(
                self.language_combo.currentData()
            ),
            selected_provider=provider,
            enrich_missing_fields=(
                self.enrich_checkbox.isChecked()
            ),
            apple_country=str(
                self.country_combo.currentData()
            ),
            feature_handling=str(
                self.feature_combo.currentData()
            ),
            selected_cover_source=cover,
            cover_fallback_enabled=(
                self.cover_fallback_checkbox.isChecked()
            ),
            minimum_cover_size=(
                self.minimum_cover_size_spin.value()
            ),
            artist_folder_levels_up=(
                self.artist_levels_spin.value()
            ),
            embedded_cover_size=1000,
            embedded_cover_quality=100,
            folder_cover_size=400,
            folder_cover_quality=80,
            audio_analysis_parallel_jobs=int(
                self.parallel_jobs_combo.currentData()
            ),
            music_sources=self._selected_sources(),
            load_sources_on_startup=(
                self.load_sources_checkbox.isChecked()
            ),
            scan_sources_on_startup=(
                self.scan_sources_checkbox.isChecked()
            ),
            discogs_token=self.discogs_token_edit.text().strip(),
        )

    @staticmethod
    def _set_combo_value(
        combo: QComboBox,
        value,
    ):
        index = combo.findData(value)

        if index >= 0:
            combo.setCurrentIndex(index)
