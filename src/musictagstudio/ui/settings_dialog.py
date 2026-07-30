from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
import logging
import threading

logger = logging.getLogger(__name__)

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QSettings,
    QThreadPool,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..cover_source_catalog import COVER_SOURCES
from ..core.normalizers import normalize_candidate
from ..models.song import Song
from ..services.rename import build_new_name
from ..models.metadata import MetadataCandidate
from ..provider_catalog import PROVIDERS
from ..library_sources import MusicSource, new_source
from ..providers import http_cache
from ..settings import DEFAULT_CONFIG_PATH, AppSettings
from ..settings import apply_request_intervals
from ..provider_diagnostics import check_provider_connections
from ..secret_store import (
    GENIUS_ACCESS_TOKEN,
    SPOTIFY_CLIENT_SECRET,
    TIDAL_GRANTED_SCOPE,
    TIDAL_CLIENT_SECRET,
    get_secret,
    set_secret,
)
from ..providers.oauth_catalog import CatalogProviderError
from ..providers.tidal_auth import (
    authorize_in_browser,
    disconnect_tidal,
    tidal_is_connected,
)
from .. import licensing_keygen as keygen
from ..i18n import SUPPORTED_LANGUAGES, tr
from ..licensing import load_license, machine_fingerprint


STATUS_STYLES = {
    "supported": ("color:#2e9d50;font-weight:600;"),
    "setup_required": ("color:#c28b00;font-weight:600;"),
    "unsupported": ("color:#d04a4a;font-weight:600;"),
}


# Tag-Felder, deren Schreiben einzeln an-/abschaltbar ist (wie history._TAG_FIELDS).
TAG_FIELDS: tuple[str, ...] = (
    "title",
    "artist",
    "album_artist",
    "album",
    "genre",
    "year",
    "track",
    "total_tracks",
    "disc",
    "total_discs",
    "isrc",
    "label",
    "copyright",
    "composer",
    "comment",
)


def _license_active_text(language: str, name: str, expiry: str) -> str:
    """Statuszeile mit Ablaufdatum (oder 'Lebenslang' bei unbefristet)."""
    display_name = name or "—"
    if not expiry:
        return tr("license_active_perpetual", language, name=display_name)
    try:
        parsed = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        date_text = parsed.strftime("%d.%m.%Y")
    except ValueError:
        date_text = expiry
    return tr("license_active_until", language, name=display_name, date=date_text)


class _LicenseStatusSignals(QObject):
    # (aktiv, Lizenzname, Ablaufdatum-ISO, geprüfter Schlüssel) – der Schlüssel
    # dient dazu, veraltete Antworten zu verwerfen, falls der Nutzer
    # weitergetippt hat. Ablaufdatum ist leer bei unbefristeten Lizenzen.
    done = Signal(bool, str, str, str)


class _LicenseStatusCheck(QRunnable):
    """Prüft einen Lizenzschlüssel online (Keygen) für die Statusanzeige."""

    def __init__(self, license_key: str, fingerprint: str) -> None:
        super().__init__()
        self._key = license_key
        self._fingerprint = fingerprint
        self.signals = _LicenseStatusSignals()

    def run(self) -> None:
        cache_path = keygen.default_cache_path()
        active, name = keygen.check_and_cache(
            self._key,
            self._fingerprint,
            now=datetime.now(),
            cache_path=cache_path,
        )
        # Das Ablaufdatum steht nach der Prüfung im Cache (leer = unbefristet).
        expiry = ""
        if active:
            cached = keygen.load_cache(cache_path)
            expiry = cached.expiry if cached is not None else ""
        try:
            self.signals.done.emit(active, name, expiry, self._key)
        except RuntimeError:
            # Dialog wurde während der Prüfung geschlossen -> Ergebnis egal.
            pass


class _MachineDeactivateSignals(QObject):
    done = Signal(bool)


class _MachineDeactivate(QRunnable):
    """Gibt die aktuelle Maschine bei Keygen frei (Hintergrund)."""

    def __init__(self, license_key: str, fingerprint: str) -> None:
        super().__init__()
        self._key = license_key
        self._fingerprint = fingerprint
        self.signals = _MachineDeactivateSignals()

    def run(self) -> None:
        try:
            ok = keygen.deactivate_this_machine(
                self._key,
                self._fingerprint,
                cache_path=keygen.default_cache_path(),
            )
        except Exception:
            # Jeder Fehler (Netz, JSON, ...) muss zu ok=False führen, damit das
            # done-Signal garantiert kommt und der Status nicht hängen bleibt.
            ok = False
        try:
            self.signals.done.emit(ok)
        except RuntimeError:
            pass


class SettingsDialog(QDialog):
    settings_saved = Signal(object)
    tidal_login_finished = Signal(bool, str)
    provider_diagnostics_finished = Signal(object)

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
        self.tidal_login_finished.connect(self._on_tidal_login_finished)
        self.provider_diagnostics_finished.connect(
            self._on_provider_diagnostics_finished
        )
        self.ui_settings = QSettings("MusicTagStudio", "MusicTagStudio")
        language = settings.language
        self.language = language

        if not self.embedded:
            self.setWindowTitle(tr("settings_page", language))
            self.resize(740, 860)

        outer_layout = QVBoxLayout(self)
        self.settings_tabs = QTabWidget()

        # Jeder Reiter ist eine eigene, scrollbare Seite.
        appearance_page = self._add_settings_tab(tr("tab_appearance", language))
        library_page = self._add_settings_tab(tr("tab_library", language))
        sources_page = self._add_settings_tab(tr("tab_sources", language))
        naming_page = self._add_settings_tab(tr("tab_naming", language))
        license_page = self._add_settings_tab(tr("tab_license", language))
        self._license_tab_index = self.settings_tabs.count() - 1

        appearance = QGroupBox(tr("appearance", language))
        appearance_form = QFormLayout(appearance)

        self.theme_combo = QComboBox()

        for label, data in (
            (tr("theme_auto", language), "automatic"),
            (tr("theme_light", language), "light"),
            (tr("theme_dark", language), "dark"),
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
            tr("theme", language),
            self.theme_combo,
        )

        self.theme_style_combo = QComboBox()
        for label, data in (
            ("MusicTagStudio", "standard"),
            (tr("theme_apple", language), "apple"),
        ):
            self.theme_style_combo.addItem(
                label,
                data,
            )
        self._set_combo_value(
            self.theme_style_combo,
            settings.theme_style,
        )
        appearance_form.addRow(
            tr("design_label", language),
            self.theme_style_combo,
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
            tr("language", language),
            self.language_combo,
        )

        self.font_scale_combo = QComboBox()
        for label_key, value in (
            ("text_size_small", 0.85),
            ("text_size_normal", 1.0),
            ("text_size_large", 1.15),
            ("text_size_xlarge", 1.3),
            ("text_size_xxlarge", 1.5),
        ):
            self.font_scale_combo.addItem(tr(label_key, language), value)
        self._set_combo_value(
            self.font_scale_combo,
            self._closest_font_scale(settings.font_scale),
        )
        appearance_form.addRow(
            tr("text_size", language),
            self.font_scale_combo,
        )
        appearance_page.addWidget(appearance)

        library = QGroupBox(tr("music_sources", language))
        library_layout = QVBoxLayout(library)
        library_info = QLabel(
            tr("library_sources_info", language)
        )
        library_info.setWordWrap(True)
        library_layout.addWidget(library_info)

        self.source_table = QTableWidget(
            0,
            4,
        )
        self.source_table.setHorizontalHeaderLabels(
            [
                tr("col_active", language),
                tr("col_name", language),
                tr("col_path", language),
                tr("col_status", language),
            ]
        )
        self.source_table.horizontalHeader().setStretchLastSection(True)
        library_layout.addWidget(self.source_table)

        source_buttons = QHBoxLayout()
        self.add_source_button = QPushButton(tr("add_source", language))
        self.add_source_button.clicked.connect(self._add_source)
        self.remove_source_button = QPushButton(tr("remove_source", language))
        self.remove_source_button.clicked.connect(self._remove_source)
        source_buttons.addWidget(self.add_source_button)
        source_buttons.addWidget(self.remove_source_button)
        source_buttons.addStretch()
        library_layout.addLayout(source_buttons)

        self.load_sources_checkbox = QCheckBox(
            tr("load_sources_startup", language)
        )
        self.load_sources_checkbox.setChecked(settings.load_sources_on_startup)
        library_layout.addWidget(self.load_sources_checkbox)

        self.scan_sources_checkbox = QCheckBox(
            tr("scan_sources_startup", language)
        )
        self.scan_sources_checkbox.setChecked(settings.scan_sources_on_startup)
        library_layout.addWidget(self.scan_sources_checkbox)

        self._populate_sources(settings.music_sources)
        library_page.addWidget(library)

        providers = QGroupBox(tr("metadata_source", language))
        provider_layout = QVBoxLayout(providers)
        provider_info = QLabel(
            tr("provider_priority_info", language)
        )
        provider_info.setWordWrap(True)
        provider_layout.addWidget(provider_info)

        self.provider_group = QButtonGroup(self)
        self.provider_group.setExclusive(True)

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
                item.catalog_size,
            )

        self.provider_buttons.get(
            settings.selected_provider,
            self.provider_buttons["apple_music"],
        ).setChecked(True)

        self.enrich_checkbox = QCheckBox(
            tr("enrich_missing", language)
        )
        self.enrich_checkbox.setChecked(settings.enrich_missing_fields)
        provider_layout.addWidget(self.enrich_checkbox)

        self.country_combo = QComboBox()

        for code, name_key in (
            ("DE", "country_de"),
            ("AT", "country_at"),
            ("CH", "country_ch"),
            ("US", "country_us"),
            ("GB", "country_gb"),
        ):
            self.country_combo.addItem(
                tr(
                    "country_line",
                    language,
                    name=tr(name_key, language),
                    code=code,
                ),
                code,
            )

        self._set_combo_value(
            self.country_combo,
            settings.apple_country,
        )
        country_form = QFormLayout()
        country_form.addRow(
            tr("apple_store", language),
            self.country_combo,
        )
        provider_layout.addLayout(country_form)
        sources_page.addWidget(providers)

        covers = QGroupBox(tr("cover_sources", language))
        cover_layout = QVBoxLayout(covers)
        cover_info = QLabel(
            tr("cover_sources_info", language)
        )
        cover_info.setWordWrap(True)
        cover_layout.addWidget(cover_info)

        self.cover_group = QButtonGroup(self)
        self.cover_group.setExclusive(True)

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
            self.cover_buttons["apple_music"],
        ).setChecked(True)

        self.cover_fallback_checkbox = QCheckBox(
            tr("cover_fallback", language)
        )
        self.cover_fallback_checkbox.setChecked(settings.cover_fallback_enabled)
        cover_layout.addWidget(self.cover_fallback_checkbox)

        cover_form = QFormLayout()

        self.minimum_cover_size_spin = QSpinBox()
        self.minimum_cover_size_spin.setRange(
            100,
            10000,
        )
        self.minimum_cover_size_spin.setValue(settings.minimum_cover_size)
        self.minimum_cover_size_spin.setSuffix(" px")
        cover_form.addRow(
            tr("min_resolution", language),
            self.minimum_cover_size_spin,
        )

        self.artist_levels_spin = QSpinBox()
        self.artist_levels_spin.setRange(
            1,
            5,
        )
        self.artist_levels_spin.setValue(settings.artist_folder_levels_up)
        self.artist_levels_spin.setToolTip(
            tr("artist_levels_tip", language)
        )
        cover_form.addRow(
            tr("artist_folder_at", language),
            self.artist_levels_spin,
        )

        cover_layout.addLayout(cover_form)
        sources_page.addWidget(covers)

        audio_analysis = QGroupBox(tr("audio_analysis_group", language))
        audio_form = QFormLayout(audio_analysis)

        self.parallel_jobs_combo = QComboBox()
        self.parallel_jobs_combo.addItem(
            tr("auto_option", language),
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
            tr("parallel_jobs_tip", language)
        )
        audio_form.addRow(
            tr("parallel_analyses", language),
            self.parallel_jobs_combo,
        )

        self.exact_album_gain_check = QCheckBox(
            tr("exact_album_gain", language)
        )
        self.exact_album_gain_check.setChecked(
            settings.audio_analysis_exact_album_gain
        )
        self.exact_album_gain_check.setToolTip(
            tr("exact_album_gain_tip", language)
        )
        audio_form.addRow("", self.exact_album_gain_check)
        sources_page.addWidget(audio_analysis)

        online_catalogs = QGroupBox(tr("online_catalogs", language))
        online_catalogs_form = QFormLayout(online_catalogs)
        self.discogs_token_edit = QLineEdit(settings.discogs_token)
        self.discogs_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.discogs_token_edit.setPlaceholderText(tr("discogs_token_placeholder", language))
        self.discogs_token_edit.setToolTip(
            tr("discogs_token_tip", language)
        )
        online_catalogs_form.addRow(
            tr("discogs_token_label", language),
            self.discogs_token_edit,
        )
        discogs_info = QLabel(
            tr("discogs_info", language)
        )
        discogs_info.setWordWrap(True)
        online_catalogs_form.addRow(discogs_info)

        catalog_sizes = QLabel(tr("online_catalog_sizes", language))
        catalog_sizes.setWordWrap(True)
        catalog_sizes.setStyleSheet("color: palette(mid); font-size: 11px;")
        catalog_sizes.setToolTip(tr("catalog_size_tip", language))
        online_catalogs_form.addRow(catalog_sizes)

        self.acoustid_key_edit = QLineEdit(settings.acoustid_api_key)
        self.acoustid_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.acoustid_key_edit.setPlaceholderText(
            tr("acoustid_placeholder", language)
        )
        self.acoustid_key_edit.setToolTip(
            tr("acoustid_tip", language)
        )
        online_catalogs_form.addRow(
            tr("acoustid_label", language),
            self.acoustid_key_edit,
        )
        self.fpcalc_path_edit = QLineEdit(settings.fpcalc_path)
        self.fpcalc_path_edit.setPlaceholderText(
            tr("fpcalc_placeholder", language)
        )
        self.fpcalc_path_edit.setToolTip(
            tr("fpcalc_tip", language)
        )
        online_catalogs_form.addRow(
            tr("fpcalc_label", language),
            self.fpcalc_path_edit,
        )

        self.tidal_client_id_edit = QLineEdit(settings.tidal_client_id)
        self.tidal_client_id_edit.setPlaceholderText("TIDAL Client ID")
        online_catalogs_form.addRow(
            "TIDAL Client ID:",
            self.tidal_client_id_edit,
        )
        self.tidal_client_secret_edit = QLineEdit(get_secret(TIDAL_CLIENT_SECRET))
        self.tidal_client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.tidal_client_secret_edit.setPlaceholderText("TIDAL Client Secret")
        self.tidal_client_secret_edit.setToolTip(
            tr("windows_credential_tip", language)
        )
        online_catalogs_form.addRow(
            "TIDAL Client Secret:",
            self.tidal_client_secret_edit,
        )
        tidal_connection_layout = QHBoxLayout()
        self.tidal_connect_button = QPushButton(tr("tidal_connect", language))
        self.tidal_disconnect_button = QPushButton(tr("tidal_disconnect", language))
        self.tidal_connection_status = QLabel()
        tidal_connection_layout.addWidget(self.tidal_connect_button)
        tidal_connection_layout.addWidget(self.tidal_disconnect_button)
        tidal_connection_layout.addWidget(self.tidal_connection_status, 1)
        online_catalogs_form.addRow(
            tr("tidal_account", language),
            tidal_connection_layout,
        )
        self.tidal_connect_button.clicked.connect(self._connect_tidal)
        self.tidal_disconnect_button.clicked.connect(self._disconnect_tidal)
        self._update_tidal_connection_status()

        self.spotify_client_id_edit = QLineEdit(settings.spotify_client_id)
        self.spotify_client_id_edit.setPlaceholderText("Spotify Client ID")
        online_catalogs_form.addRow(
            "Spotify Client ID:",
            self.spotify_client_id_edit,
        )
        self.spotify_client_secret_edit = QLineEdit(get_secret(SPOTIFY_CLIENT_SECRET))
        self.spotify_client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.spotify_client_secret_edit.setPlaceholderText("Spotify Client Secret")
        self.spotify_client_secret_edit.setToolTip(
            tr("windows_credential_tip", language)
        )
        online_catalogs_form.addRow(
            "Spotify Client Secret:",
            self.spotify_client_secret_edit,
        )
        self.genius_access_token_edit = QLineEdit(get_secret(GENIUS_ACCESS_TOKEN))
        self.genius_access_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.genius_access_token_edit.setPlaceholderText("Genius Client Access Token")
        self.genius_access_token_edit.setToolTip(
            tr("windows_credential_tip", language)
        )
        online_catalogs_form.addRow(
            "Genius Access Token:",
            self.genius_access_token_edit,
        )
        streaming_info = QLabel(
            tr("streaming_info", language)
        )
        streaming_info.setWordWrap(True)
        online_catalogs_form.addRow(streaming_info)

        pacing_layout = QHBoxLayout()
        self.apple_interval_spin = QDoubleSpinBox()
        self.apple_interval_spin.setRange(0.5, 10.0)
        self.apple_interval_spin.setSingleStep(0.5)
        self.apple_interval_spin.setSuffix(" s")
        self.apple_interval_spin.setValue(settings.apple_request_interval_seconds)
        self.genius_interval_spin = QDoubleSpinBox()
        self.genius_interval_spin.setRange(0.5, 10.0)
        self.genius_interval_spin.setSingleStep(0.5)
        self.genius_interval_spin.setSuffix(" s")
        self.genius_interval_spin.setValue(settings.genius_request_interval_seconds)
        pacing_layout.addWidget(QLabel("Apple:"))
        pacing_layout.addWidget(self.apple_interval_spin)
        pacing_layout.addWidget(QLabel("Genius:"))
        pacing_layout.addWidget(self.genius_interval_spin)
        pacing_layout.addStretch(1)
        online_catalogs_form.addRow(tr("request_interval", language), pacing_layout)

        self.apple_web_search_checkbox = QCheckBox(
            tr("apple_web_fallback", language)
        )
        self.apple_web_search_checkbox.setChecked(
            settings.apple_web_search_enabled
        )
        self.apple_web_search_checkbox.setToolTip(
            tr("apple_web_fallback_tip", language)
        )
        online_catalogs_form.addRow(self.apple_web_search_checkbox)

        self.preview_source_combo = QComboBox()
        self.preview_source_combo.addItem("Deezer", "deezer")
        self.preview_source_combo.addItem("Apple Music", "apple_music")
        preview_index = self.preview_source_combo.findData(
            settings.preview_source
        )
        self.preview_source_combo.setCurrentIndex(
            preview_index if preview_index >= 0 else 0
        )
        self.preview_source_combo.setToolTip(
            tr("preview_source_setting_tip", language)
        )
        online_catalogs_form.addRow(
            tr("preview_source_label", language),
            self.preview_source_combo,
        )

        self.provider_check_button = QPushButton(tr("check_access", language))
        self.provider_check_button.clicked.connect(self._check_provider_connections)
        online_catalogs_form.addRow(self.provider_check_button)

        self.clear_cache_button = QPushButton(tr("clear_provider_cache", language))
        self.clear_cache_button.setToolTip(
            tr("clear_cache_tip", language)
        )
        self.clear_cache_button.clicked.connect(self._clear_provider_cache)
        online_catalogs_form.addRow(self.clear_cache_button)
        self.provider_status_labels = {}
        for provider in ("Discogs", "TIDAL", "Spotify", "Genius"):
            label = QLabel(self._stored_provider_status(provider))
            label.setWordWrap(True)
            self.provider_status_labels[provider] = label
            online_catalogs_form.addRow(
                tr("provider_status_row", language, provider=provider), label
            )
        sources_page.addWidget(online_catalogs)

        normalization = QGroupBox(tr("normalization", language))
        normalization_form = QFormLayout(normalization)

        self.feature_combo = QComboBox()

        for label_key, data in (
            ("feature_artist_only", "artist_only"),
            ("feature_title_artist", "title_and_artist"),
            ("feature_source_style", "source"),
        ):
            self.feature_combo.addItem(
                tr(label_key, language),
                data,
            )

        self._set_combo_value(
            self.feature_combo,
            settings.feature_handling,
        )
        normalization_form.addRow(
            tr("feature_artist_label", language),
            self.feature_combo,
        )
        self.feature_preview = QLabel()
        self.feature_preview.setObjectName("featureHandlingPreview")
        self.feature_preview.setWordWrap(True)
        normalization_form.addRow(
            tr("example_label", language),
            self.feature_preview,
        )
        self.feature_combo.currentIndexChanged.connect(self._update_feature_preview)
        self._update_feature_preview()
        naming_page.addWidget(normalization)

        rename = QGroupBox(tr("rename_group", language))
        rename_form = QFormLayout(rename)
        self.rename_pattern_edit = QLineEdit(settings.rename_pattern)
        self.rename_pattern_edit.setPlaceholderText("{track} - {title}")
        rename_form.addRow(
            tr("rename_pattern_label", language),
            self.rename_pattern_edit,
        )
        self.rename_preview = QLabel()
        self.rename_preview.setObjectName("renamePreview")
        self.rename_preview.setWordWrap(True)
        rename_form.addRow(tr("rename_preview_label", language), self.rename_preview)
        rename_hint = QLabel(tr("rename_pattern_hint", language))
        rename_hint.setWordWrap(True)
        rename_form.addRow("", rename_hint)
        self.rename_pattern_edit.textChanged.connect(self._update_rename_preview)
        # Vorschau reagiert auch auf die Feature-Künstler-Einstellung, da diese
        # Titel/Künstler (und damit den Dateinamen) verändert.
        self.feature_combo.currentIndexChanged.connect(self._update_rename_preview)
        self._update_rename_preview()
        naming_page.addWidget(rename)

        metadata_box = QGroupBox(tr("embedded_tags_group", language))
        metadata_layout = QVBoxLayout(metadata_box)
        metadata_hint = QLabel(tr("embedded_tags_hint", language))
        metadata_hint.setWordWrap(True)
        metadata_layout.addWidget(metadata_hint)
        toggle_row = QHBoxLayout()
        enable_all = QPushButton(tr("enable_all", language))
        enable_all.clicked.connect(lambda: self._set_all_tag_fields(True))
        disable_all = QPushButton(tr("disable_all", language))
        disable_all.clicked.connect(lambda: self._set_all_tag_fields(False))
        toggle_row.addWidget(enable_all)
        toggle_row.addWidget(disable_all)
        toggle_row.addStretch()
        metadata_layout.addLayout(toggle_row)
        tag_grid = QGridLayout()
        self.tag_field_checks: dict[str, QCheckBox] = {}
        for index, field in enumerate(TAG_FIELDS):
            check = QCheckBox(tr(f"field_{field}", language))
            check.setChecked(field not in settings.disabled_tag_fields)
            self.tag_field_checks[field] = check
            tag_grid.addWidget(check, index // 2, index % 2)
        metadata_layout.addLayout(tag_grid)
        naming_page.addWidget(metadata_box)

        license_box = QGroupBox(tr("license_group", language))
        license_form = QFormLayout(license_box)
        self.license_key_edit = QLineEdit(settings.license_key)
        self.license_key_edit.setPlaceholderText("…")
        license_form.addRow(
            tr("license_key_label", language),
            self.license_key_edit,
        )
        self.license_status_label = QLabel()
        self.license_status_label.setWordWrap(True)
        license_form.addRow(tr("license_status", language), self.license_status_label)
        self.license_deactivate_button = QPushButton(
            tr("license_deactivate", language)
        )
        self.license_deactivate_button.setToolTip(
            tr("license_deactivate_tip", language)
        )
        self.license_deactivate_button.clicked.connect(self._deactivate_machine)
        license_form.addRow("", self.license_deactivate_button)
        self._license_status_workers: set = set()
        # Entprellte Online-Prüfung: kurz nach dem Tippen/Einfügen automatisch
        # prüfen, ohne dass der Nutzer das Feld verlassen oder speichern muss.
        self._license_check_timer = QTimer(self)
        self._license_check_timer.setSingleShot(True)
        self._license_check_timer.setInterval(600)
        self._license_check_timer.timeout.connect(self._check_license_online)
        self.license_key_edit.textChanged.connect(self._on_license_key_changed)
        # Bei Enter/Fokusverlust sofort prüfen (ohne auf den Timer zu warten).
        self.license_key_edit.editingFinished.connect(self._check_license_online)
        self._update_license_status()
        self._check_license_online()
        license_page.addWidget(license_box)

        purchase_box = self._build_purchase_box(language)
        if purchase_box is not None:
            license_page.addWidget(purchase_box)

        for page in (
            appearance_page,
            library_page,
            sources_page,
            naming_page,
            license_page,
        ):
            page.addStretch()

        outer_layout.addWidget(self.settings_tabs)

        if self.embedded:
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save)
            button_box.accepted.connect(self._save_embedded)
        else:
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save
                | QDialogButtonBox.StandardButton.Cancel
            )
            button_box.accepted.connect(self.accept)
            button_box.rejected.connect(self.reject)
        self.open_config_button = button_box.addButton(
            tr("open_config_folder", language),
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        self.open_config_button.clicked.connect(self._open_config_folder)
        self.reset_defaults_button = button_box.addButton(
            tr("reset_defaults", language),
            QDialogButtonBox.ButtonRole.ResetRole,
        )
        self.reset_defaults_button.clicked.connect(self._reset_to_defaults)
        self.button_box = button_box
        self._update_button_texts()
        self.language_combo.currentIndexChanged.connect(self._update_button_texts)
        outer_layout.addWidget(button_box)

    def focus_license_tab(self) -> None:
        """Wechselt zum Lizenz-Reiter und fokussiert das Schlüsselfeld."""
        self.settings_tabs.setCurrentIndex(self._license_tab_index)
        self.license_key_edit.setFocus()

    def _build_purchase_box(self, language: str) -> QGroupBox | None:
        """Kauf-Buttons je Laufzeit (nur eingerichtete PayPal-Buttons)."""
        from ..purchase import configured_options

        options = configured_options()
        if not options:
            return None

        box = QGroupBox(tr("premium_buy_heading", language))
        layout = QVBoxLayout(box)

        buttons_row = QHBoxLayout()
        for option in options:
            label = tr(option.label_key, language)
            if option.price:
                label = f"{label} · {option.price}"
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, url=option.url: QDesktopServices.openUrl(
                    QUrl(url)
                )
            )
            buttons_row.addWidget(button)
        layout.addLayout(buttons_row)

        hint = QLabel(tr("premium_buy_hint", language))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid); font-size: 11px;")
        layout.addWidget(hint)
        return box

    def _add_settings_tab(self, title: str) -> QVBoxLayout:
        """Legt einen scrollbaren Reiter an und gibt dessen Layout zurück."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.settings_tabs.addTab(scroll, title)
        return page_layout

    def _set_all_tag_fields(self, enabled: bool) -> None:
        for check in self.tag_field_checks.values():
            check.setChecked(enabled)

    def _open_config_folder(self) -> None:
        folder = Path(DEFAULT_CONFIG_PATH).resolve().parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _reset_to_defaults(self) -> None:
        """Setzt Darstellungs-, Benennungs- und Normalisierungs-Optionen zurück.

        Musikquellen, Provider-Auswahl, API-Schlüssel und die Lizenz bleiben
        bewusst erhalten (kein Datenverlust); nur reine Vorlieben werden auf den
        Auslieferungszustand gesetzt.
        """
        confirmed = (
            QMessageBox.question(
                self,
                tr("reset_defaults", self.language),
                tr("reset_defaults_confirm_msg", self.language),
            )
            == QMessageBox.StandardButton.Yes
        )
        if not confirmed:
            return
        defaults = AppSettings()
        self._set_combo_value(self.theme_combo, defaults.theme)
        self._set_combo_value(self.theme_style_combo, defaults.theme_style)
        self._set_combo_value(
            self.font_scale_combo, self._closest_font_scale(defaults.font_scale)
        )
        self.rename_pattern_edit.setText(defaults.rename_pattern)
        self._set_combo_value(self.feature_combo, defaults.feature_handling)
        self._update_rename_preview()

    def _update_button_texts(
        self,
        _index: int = -1,
    ) -> None:
        language = str(self.language_combo.currentData() or "automatic")
        save_button = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText(tr("save", language))
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setText(tr("cancel", language))

    def _populate_sources(
        self,
        sources: tuple[MusicSource, ...],
    ) -> None:
        self.source_table.setRowCount(0)

        for source in sources:
            self._append_source_row(source)

    def _append_source_row(
        self,
        source: MusicSource,
    ) -> None:
        row = self.source_table.rowCount()
        self.source_table.insertRow(row)

        active = QTableWidgetItem()
        active.setFlags(active.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        active.setCheckState(
            (Qt.CheckState.Checked if source.enabled else Qt.CheckState.Unchecked)
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
            QTableWidgetItem(source.name),
        )
        self.source_table.setItem(
            row,
            2,
            QTableWidgetItem(source.path),
        )
        status = (
            tr("source_reachable", self.language)
            if Path(source.path).is_dir()
            else tr("source_path_missing", self.language)
        )
        status_item = QTableWidgetItem(status)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
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
            tr("select_music_source", self.language),
            "",
        )

        if not folder:
            return

        self._append_source_row(new_source(folder))

    def _remove_source(
        self,
    ) -> None:
        row = self.source_table.currentRow()

        if row >= 0:
            self.source_table.removeRow(row)

    def _selected_sources(
        self,
    ) -> tuple[MusicSource, ...]:
        sources: list[MusicSource] = []

        for row in range(self.source_table.rowCount()):
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

            if active is None or name_item is None or path_item is None:
                continue

            path_value = path_item.text().strip()

            if not path_value:
                continue

            source_id = str(active.data(Qt.ItemDataRole.UserRole) or "").strip()

            if not source_id:
                source_id = new_source(path_value).source_id

            sources.append(
                MusicSource(
                    source_id=source_id,
                    name=name_item.text().strip()
                    or Path(path_value).name
                    or path_value,
                    path=path_value,
                    enabled=(active.checkState() == Qt.CheckState.Checked),
                )
            )

        return tuple(sources)

    def _update_rename_preview(self, _index: int = -1) -> None:
        """Live-Vorschau des Dateinamens für das aktuelle Schema.

        Nutzt dasselbe Beispiel wie die Feature-Künstler-Vorschau, damit die
        Vorschau sich auch bei einer Änderung dieser Einstellung mitändert.
        """
        example = MetadataCandidate(
            source="preview",
            title="California Love (feat. Dr. Dre)",
            artist="2Pac",
        )
        normalized = normalize_candidate(
            example,
            feature_handling=str(self.feature_combo.currentData()),
        )
        song = Song(
            title=normalized.title,
            artist=normalized.artist,
            album_artist="2Pac",
            album="All Eyez on Me",
            genre="Hip-Hop",
            year="1996",
            track="4",
            disc="1",
            path="beispiel.flac",
        )
        pattern = self.rename_pattern_edit.text().strip() or "{track} - {title}"
        self.rename_preview.setText(build_new_name(song, pattern))
        self.rename_preview.setStyleSheet(
            "padding: 8px 10px;"
            "border: 1px solid palette(mid);"
            "border-radius: 7px;"
            "background: palette(alternate-base);"
        )

    def _update_feature_preview(
        self,
        _index: int = -1,
    ) -> None:
        example = MetadataCandidate(
            source="preview",
            title="California Love (feat. Dr. Dre)",
            artist="2Pac",
        )
        result = normalize_candidate(
            example,
            feature_handling=str(self.feature_combo.currentData()),
        )
        self.feature_preview.setText(
            tr(
                "feature_preview_text",
                self.language,
                title=result.title,
                artist=result.artist,
            )
        )
        self.feature_preview.setStyleSheet(
            "padding: 8px 10px;"
            "border: 1px solid palette(mid);"
            "border-radius: 7px;"
            "background: palette(alternate-base);"
        )

    def _save_embedded(
        self,
    ) -> None:
        self._save_streaming_secrets()
        new_settings = self.selected_settings()
        self.initial_settings = new_settings
        self.settings_saved.emit(new_settings)

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
        catalog_size="",
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

        status_label = QLabel(status_text)
        status_label.setStyleSheet(STATUS_STYLES[status])
        status_label.setToolTip(tooltip)
        row.setToolTip(tooltip)

        group.addButton(button)
        storage[item_id] = button

        row_layout.addWidget(button)
        if catalog_size:
            size_label = QLabel(catalog_size)
            size_label.setStyleSheet("color: palette(mid); font-size: 11px;")
            size_label.setToolTip(tr("catalog_size_tip", self.language))
            row_layout.addWidget(size_label)
        row_layout.addStretch()
        row_layout.addWidget(status_label)
        layout.addWidget(row)

    def selected_settings(
        self,
    ) -> AppSettings:
        provider = next(
            (
                item_id
                for item_id, button in self.provider_buttons.items()
                if button.isChecked()
            ),
            "apple_music",
        )
        cover = next(
            (
                item_id
                for item_id, button in self.cover_buttons.items()
                if button.isChecked()
            ),
            "apple_music",
        )

        return replace(
            self.initial_settings,
            theme=str(self.theme_combo.currentData()),
            theme_style=str(self.theme_style_combo.currentData()),
            language=str(self.language_combo.currentData()),
            font_scale=float(self.font_scale_combo.currentData() or 1.0),
            rename_pattern=(
                self.rename_pattern_edit.text().strip() or "{track} - {title}"
            ),
            license_key=self.license_key_edit.text().strip(),
            disabled_tag_fields=tuple(
                field
                for field, check in self.tag_field_checks.items()
                if not check.isChecked()
            ),
            selected_provider=provider,
            enrich_missing_fields=(self.enrich_checkbox.isChecked()),
            apple_country=str(self.country_combo.currentData()),
            feature_handling=str(self.feature_combo.currentData()),
            selected_cover_source=cover,
            cover_fallback_enabled=(self.cover_fallback_checkbox.isChecked()),
            minimum_cover_size=(self.minimum_cover_size_spin.value()),
            artist_folder_levels_up=(self.artist_levels_spin.value()),
            embedded_cover_size=1000,
            embedded_cover_quality=100,
            folder_cover_size=400,
            folder_cover_quality=80,
            audio_analysis_parallel_jobs=int(self.parallel_jobs_combo.currentData()),
            audio_analysis_exact_album_gain=self.exact_album_gain_check.isChecked(),
            music_sources=self._selected_sources(),
            load_sources_on_startup=(self.load_sources_checkbox.isChecked()),
            scan_sources_on_startup=(self.scan_sources_checkbox.isChecked()),
            discogs_token=self.discogs_token_edit.text().strip(),
            acoustid_api_key=self.acoustid_key_edit.text().strip(),
            fpcalc_path=self.fpcalc_path_edit.text().strip(),
            tidal_client_id=self.tidal_client_id_edit.text().strip(),
            spotify_client_id=self.spotify_client_id_edit.text().strip(),
            apple_request_interval_seconds=self.apple_interval_spin.value(),
            genius_request_interval_seconds=self.genius_interval_spin.value(),
            apple_web_search_enabled=(
                self.apple_web_search_checkbox.isChecked()
            ),
            preview_source=str(
                self.preview_source_combo.currentData()
            ),
        )

    def accept(self) -> None:
        self._save_streaming_secrets()
        apply_request_intervals(self.selected_settings())
        super().accept()

    def _save_streaming_secrets(self) -> None:
        set_secret(
            TIDAL_CLIENT_SECRET,
            self.tidal_client_secret_edit.text(),
        )
        set_secret(
            SPOTIFY_CLIENT_SECRET,
            self.spotify_client_secret_edit.text(),
        )
        set_secret(
            GENIUS_ACCESS_TOKEN,
            self.genius_access_token_edit.text(),
        )
        for provider, configured in (
            ("Discogs", bool(self.discogs_token_edit.text().strip())),
            ("TIDAL", bool(self.tidal_client_id_edit.text().strip())),
            ("Spotify", bool(self.spotify_client_id_edit.text().strip())),
            ("Genius", bool(self.genius_access_token_edit.text().strip())),
        ):
            self.ui_settings.setValue(
                f"provider_diagnostics/{provider}/configured",
                configured,
            )

    def _connect_tidal(self) -> None:
        client_id = self.tidal_client_id_edit.text().strip()
        if not client_id:
            self.tidal_connection_status.setText(
                "Bitte zuerst die Client ID eintragen."
            )
            self.tidal_connection_status.setStyleSheet(STATUS_STYLES["unsupported"])
            return
        self._save_streaming_secrets()
        self.tidal_connect_button.setEnabled(False)
        self.tidal_disconnect_button.setEnabled(False)
        self.tidal_connection_status.setText(tr("tidal_login_running", self.language))
        self.tidal_connection_status.setStyleSheet(STATUS_STYLES["setup_required"])

        def authorize() -> None:
            try:
                authorize_in_browser(client_id)
            except CatalogProviderError as error:
                self.tidal_login_finished.emit(False, str(error))
                return
            except Exception:
                logger.warning("Unerwarteter TIDAL-Anmeldefehler", exc_info=True)
                self.tidal_login_finished.emit(
                    False,
                    tr("tidal_login_failed", self.language),
                )
                return
            self.tidal_login_finished.emit(True, "")

        threading.Thread(
            target=authorize,
            name="tidal-browser-login",
            daemon=True,
        ).start()

    def _disconnect_tidal(self) -> None:
        disconnect_tidal()
        self._update_tidal_connection_status()

    def _on_tidal_login_finished(self, success: bool, message: str) -> None:
        self.tidal_connect_button.setEnabled(True)
        if success:
            self._update_tidal_connection_status()
            return
        self.tidal_connection_status.setText(message)
        self.tidal_connection_status.setStyleSheet(STATUS_STYLES["unsupported"])
        self.tidal_disconnect_button.setEnabled(tidal_is_connected())

    def _update_tidal_connection_status(self) -> None:
        connected = tidal_is_connected()
        if connected:
            self.ui_settings.setValue(
                "provider_diagnostics/TIDAL/scope",
                get_secret(TIDAL_GRANTED_SCOPE).strip(),
            )
        self.tidal_connection_status.setText(
            tr("tidal_connected", self.language)
            if connected
            else tr("tidal_not_connected", self.language)
        )
        self.tidal_connection_status.setStyleSheet(
            STATUS_STYLES["supported" if connected else "setup_required"]
        )
        self.tidal_connect_button.setText(
            tr("tidal_reconnect", self.language)
            if connected
            else tr("tidal_connect", self.language)
        )
        self.tidal_connect_button.setEnabled(True)
        self.tidal_disconnect_button.setEnabled(connected)

    def _clear_provider_cache(self) -> None:
        http_cache.clear()
        QMessageBox.information(
            self,
            tr("cache_cleared_title", self.language),
            tr("cache_cleared_msg", self.language),
        )

    def _check_provider_connections(self) -> None:
        self._save_streaming_secrets()
        self.provider_check_button.setEnabled(False)
        self.provider_check_button.setText(tr("checking_access", self.language))
        for label in self.provider_status_labels.values():
            label.setText(tr("checking_running", self.language))
            label.setStyleSheet(STATUS_STYLES["setup_required"])

        arguments = {
            "discogs_token": self.discogs_token_edit.text(),
            "tidal_client_id": self.tidal_client_id_edit.text(),
            "tidal_client_secret": self.tidal_client_secret_edit.text(),
            "spotify_client_id": self.spotify_client_id_edit.text(),
            "spotify_client_secret": self.spotify_client_secret_edit.text(),
            "genius_access_token": self.genius_access_token_edit.text(),
        }

        def run_checks() -> None:
            results = check_provider_connections(**arguments)
            self.provider_diagnostics_finished.emit(results)

        threading.Thread(
            target=run_checks,
            name="provider-connection-check",
            daemon=True,
        ).start()

    def _on_provider_diagnostics_finished(self, results: object) -> None:
        self.provider_check_button.setEnabled(True)
        self.provider_check_button.setText(tr("check_access", self.language))
        for result in results:
            label = self.provider_status_labels.get(result.provider)
            if label is None:
                continue
            if result.successful:
                self.ui_settings.setValue(
                    f"provider_diagnostics/{result.provider}/last_success",
                    result.checked_at,
                )
            last_success = self.ui_settings.value(
                f"provider_diagnostics/{result.provider}/last_success",
                "",
            )
            suffix = (
                tr("last_success_suffix", self.language, when=last_success)
                if last_success
                else ""
            )
            label.setText(f"{result.message}{suffix}")
            style = (
                "supported"
                if result.successful
                else (
                    "setup_required"
                    if result.status == "not_configured"
                    else "unsupported"
                )
            )
            label.setStyleSheet(STATUS_STYLES[style])

    def _stored_provider_status(self, provider: str) -> str:
        last_success = self.ui_settings.value(
            f"provider_diagnostics/{provider}/last_success",
            "",
        )
        if last_success:
            return tr("last_checked_success", self.language, when=last_success)
        return tr("not_checked_yet", self.language)

    def _on_license_key_changed(self) -> None:
        """Sofort-Anzeige aktualisieren und die Online-Prüfung entprellt anstoßen."""
        self._update_license_status()
        key = self.license_key_edit.text().strip()
        # Nur prüfen, wenn ein Keygen-Schlüssel vorliegt (kein Offline-Key).
        if key and load_license(key) is None and keygen.is_configured():
            self._license_check_timer.start()
        else:
            self._license_check_timer.stop()

    def _update_license_status(self) -> None:
        """Sofort-Anzeige ohne Netzwerk: Offline-Signatur bzw. Zwischenstand."""
        key = self.license_key_edit.text().strip()
        # Deaktivieren nur sinnvoll, wenn ein Keygen-Schlüssel vorliegt.
        self.license_deactivate_button.setEnabled(
            bool(key) and keygen.is_configured() and load_license(key) is None
        )
        if not key:
            self.license_status_label.setText(tr("license_inactive", self.language))
            return
        # Eigene, offline signierte Lizenz (make_license.py) sofort erkennen.
        license_ = load_license(key)
        if license_ is not None:
            self.license_status_label.setText(
                tr("license_active", self.language, name=license_.licensee)
            )
        elif keygen.is_configured():
            # Keygen-Schlüssel wird online geprüft -> Zwischenstand anzeigen.
            self.license_status_label.setText(tr("license_checking", self.language))
        else:
            self.license_status_label.setText(tr("license_inactive", self.language))

    def _check_license_online(self) -> None:
        key = self.license_key_edit.text().strip()
        # Nur nötig, wenn ein Schlüssel vorliegt, er nicht schon offline gültig
        # ist und Keygen konfiguriert ist.
        if not key or load_license(key) is not None or not keygen.is_configured():
            return
        self.license_status_label.setText(tr("license_checking", self.language))
        worker = _LicenseStatusCheck(key, machine_fingerprint())
        worker.setAutoDelete(False)
        self._license_status_workers.add(worker)
        worker.signals.done.connect(
            lambda active, name, expiry, checked, w=worker: self._on_license_checked(
                active, name, expiry, checked, w
            )
        )
        QThreadPool.globalInstance().start(worker)

    def _on_license_checked(
        self, active: bool, name: str, expiry: str, checked_key: str, worker
    ) -> None:
        self._license_status_workers.discard(worker)
        # Veraltete Antwort verwerfen, falls der Nutzer weitergetippt hat.
        if checked_key != self.license_key_edit.text().strip():
            return
        if active:
            self.license_status_label.setText(
                _license_active_text(self.language, name, expiry)
            )
        else:
            self.license_status_label.setText(tr("license_inactive", self.language))

    def _deactivate_machine(self) -> None:
        key = self.license_key_edit.text().strip()
        if not key or not keygen.is_configured():
            return
        confirmed = (
            QMessageBox.question(
                self,
                tr("license_deactivate", self.language),
                tr("license_deactivate_confirm_msg", self.language),
            )
            == QMessageBox.StandardButton.Yes
        )
        if not confirmed:
            return
        self.license_deactivate_button.setEnabled(False)
        self.license_status_label.setText(tr("license_checking", self.language))
        worker = _MachineDeactivate(key, machine_fingerprint())
        worker.setAutoDelete(False)
        self._license_status_workers.add(worker)
        worker.signals.done.connect(
            lambda ok, w=worker: self._on_machine_deactivated(ok, w)
        )
        QThreadPool.globalInstance().start(worker)

    def _on_machine_deactivated(self, ok: bool, worker) -> None:
        self._license_status_workers.discard(worker)
        if ok:
            # Den Schlüssel lokal entfernen und sofort speichern. Sonst würde
            # die automatische Online-Prüfung (hier und beim nächsten Start)
            # die gerade freigegebene Maschine umgehend wieder aktivieren und
            # Premium bliebe fälschlich aktiv.
            self.license_key_edit.blockSignals(True)
            self.license_key_edit.clear()
            self.license_key_edit.blockSignals(False)
            self.settings_saved.emit(self.selected_settings())
            QMessageBox.information(
                self,
                tr("license_deactivate", self.language),
                tr("license_deactivated_msg", self.language),
            )
            # Key ist leer -> zeigt "inaktiv", Knopf wird deaktiviert.
            self._update_license_status()
            return
        QMessageBox.warning(
            self,
            tr("license_deactivate", self.language),
            tr("license_deactivate_failed_msg", self.language),
        )
        # Knopf/Zwischenstand zurücksetzen und den echten Status online
        # nachziehen -- sonst bliebe die Anzeige auf "wird geprüft" hängen.
        self._update_license_status()
        self._check_license_online()

    @staticmethod
    def _closest_font_scale(value: float) -> float:
        # Auf den naechstliegenden angebotenen Wert einrasten, damit ein
        # (z. B. von Hand editierter) Zwischenwert die Auswahl nicht leer laesst.
        options = (0.85, 1.0, 1.15, 1.3, 1.5)
        try:
            target = float(value)
        except (TypeError, ValueError):
            return 1.0
        return min(options, key=lambda option: abs(option - target))

    @staticmethod
    def _set_combo_value(
        combo: QComboBox,
        value,
    ):
        index = combo.findData(value)

        if index >= 0:
            combo.setCurrentIndex(index)
