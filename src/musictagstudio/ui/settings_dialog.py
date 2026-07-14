from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..provider_catalog import PROVIDERS
from ..settings import AppSettings


STATUS_STYLES = {
    "supported": (
        "color: #2e9d50; font-weight: 600;"
    ),
    "setup_required": (
        "color: #c28b00; font-weight: 600;"
    ),
    "unsupported": (
        "color: #d04a4a; font-weight: 600;"
    ),
}


class SettingsDialog(QDialog):
    settings_saved = Signal(object)

    def __init__(
        self,
        settings: AppSettings,
        parent=None,
    ):
        super().__init__(parent)

        self.initial_settings = settings
        self.provider_buttons: dict[
            str,
            QRadioButton,
        ] = {}

        self.setWindowTitle("Einstellungen")
        self.resize(650, 720)

        layout = QVBoxLayout(self)

        appearance_group = QGroupBox("Darstellung")
        appearance_form = QFormLayout(
            appearance_group
        )

        self.theme_combo = QComboBox()
        self.theme_combo.addItem(
            "Automatisch (Windows-Einstellung)",
            "automatic",
        )
        self.theme_combo.addItem(
            "Hell",
            "light",
        )
        self.theme_combo.addItem(
            "Dunkel",
            "dark",
        )
        self._set_combo_value(
            self.theme_combo,
            settings.theme,
        )

        appearance_form.addRow(
            "Theme:",
            self.theme_combo,
        )
        layout.addWidget(appearance_group)

        providers_group = QGroupBox(
            "Metadatenquelle"
        )
        providers_layout = QVBoxLayout(
            providers_group
        )

        provider_info = QLabel(
            "Die ausgewählte Quelle besitzt Priorität. "
            "Andere bereits unterstützte Quellen können "
            "auf Wunsch ausschließlich fehlende Felder ergänzen."
        )
        provider_info.setWordWrap(True)
        providers_layout.addWidget(provider_info)

        self.provider_group = QButtonGroup(self)
        self.provider_group.setExclusive(True)

        for provider in PROVIDERS:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 3, 4, 3)

            button = QRadioButton(provider.name)
            button.setEnabled(provider.selectable)
            button.setToolTip(provider.tooltip)

            status = QLabel(provider.status_text)
            status.setStyleSheet(
                STATUS_STYLES[provider.status]
            )
            status.setToolTip(provider.tooltip)

            row.setToolTip(provider.tooltip)

            self.provider_group.addButton(button)
            self.provider_buttons[
                provider.provider_id
            ] = button

            row_layout.addWidget(button)
            row_layout.addStretch()
            row_layout.addWidget(status)

            providers_layout.addWidget(row)

        selected_button = self.provider_buttons.get(
            settings.selected_provider
        )

        if (
            selected_button is not None
            and selected_button.isEnabled()
        ):
            selected_button.setChecked(True)
        else:
            self.provider_buttons[
                "apple_music"
            ].setChecked(True)

        separator = QFrame()
        separator.setFrameShape(
            QFrame.Shape.HLine
        )
        separator.setFrameShadow(
            QFrame.Shadow.Sunken
        )
        providers_layout.addWidget(separator)

        self.enrich_checkbox = QCheckBox(
            "Fehlende Felder durch andere "
            "unterstützte Quellen ergänzen"
        )
        self.enrich_checkbox.setChecked(
            settings.enrich_missing_fields
        )
        self.enrich_checkbox.setToolTip(
            "Vorhandene Werte der ausgewählten Quelle "
            "werden nicht durch andere Quellen ersetzt. "
            "Andere Quellen füllen nur Felder, für die die "
            "bevorzugte Quelle keinen Wert geliefert hat."
        )
        providers_layout.addWidget(
            self.enrich_checkbox
        )

        country_form = QFormLayout()

        self.country_combo = QComboBox()
        for country_code, country_name in (
            ("DE", "Deutschland"),
            ("AT", "Österreich"),
            ("CH", "Schweiz"),
            ("US", "USA"),
            ("GB", "Großbritannien"),
        ):
            self.country_combo.addItem(
                f"{country_name} ({country_code})",
                country_code,
            )

        self._set_combo_value(
            self.country_combo,
            settings.apple_country,
        )

        country_form.addRow(
            "Apple-Store:",
            self.country_combo,
        )
        providers_layout.addLayout(country_form)

        layout.addWidget(providers_group)

        normalization_group = QGroupBox(
            "Normalisierung"
        )
        normalization_form = QFormLayout(
            normalization_group
        )

        self.feature_combo = QComboBox()
        self.feature_combo.addItem(
            "Gast nur im Künstlerfeld",
            "artist_only",
        )
        self.feature_combo.addItem(
            "Gast im Titel und Künstlerfeld",
            "title_and_artist",
        )
        self.feature_combo.addItem(
            "Schreibweise der Quelle beibehalten",
            "source",
        )

        self._set_combo_value(
            self.feature_combo,
            settings.feature_handling,
        )

        normalization_form.addRow(
            "Feature-Künstler:",
            self.feature_combo,
        )
        layout.addWidget(normalization_group)

        layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        save_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Save
        )
        cancel_button = self.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        )

        if save_button is not None:
            save_button.setText("Speichern")

        if cancel_button is not None:
            cancel_button.setText("Abbrechen")

        self.button_box.accepted.connect(
            self._save
        )
        self.button_box.rejected.connect(
            self.reject
        )
        layout.addWidget(self.button_box)

    def selected_settings(self) -> AppSettings:
        selected_provider = "apple_music"

        for provider_id, button in (
            self.provider_buttons.items()
        ):
            if button.isChecked():
                selected_provider = provider_id
                break

        return replace(
            self.initial_settings,
            theme=str(
                self.theme_combo.currentData()
            ),
            selected_provider=selected_provider,
            enrich_missing_fields=(
                self.enrich_checkbox.isChecked()
            ),
            apple_country=str(
                self.country_combo.currentData()
            ),
            feature_handling=str(
                self.feature_combo.currentData()
            ),
        )

    def _save(self):
        settings = self.selected_settings()
        self.settings_saved.emit(settings)
        self.accept()

    @staticmethod
    def _set_combo_value(
        combo: QComboBox,
        value: str,
    ):
        index = combo.findData(value)

        if index >= 0:
            combo.setCurrentIndex(index)
