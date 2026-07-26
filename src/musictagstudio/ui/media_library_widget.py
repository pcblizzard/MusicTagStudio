from __future__ import annotations

from pathlib import Path
from datetime import datetime
import html
import logging
import re
import webbrowser

logger = logging.getLogger(__name__)

from PySide6.QtCore import (
    QObject,
    QSettings,
    QSize,
    QRunnable,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
    Qt,
)
from PySide6.QtGui import (
    QIcon,
    QPalette,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QListView,
    QVBoxLayout,
    QWidget,
)

from ..media_library import (
    ArtistCandidate,
    ArtistSearchResult,
    DiscogsRelease,
    DiscogsCatalogHit,
    DiscogsCatalogSnapshot,
    Edition,
    ReleaseGroup,
    Track,
    fetch_release_group_editions,
    fetch_release_tracklist,
    ArtistRelationsResponse,
    ArtistSearchResponse,
    ReleaseGroupResponse,
    default_controller,
    fetch_discogs_artist_releases,
    fetch_catalog_release,
    fetch_label_releases,
    fetch_discogs_release_tracks,
    load_catalog_snapshot,
    save_catalog_snapshot,
    search_catalog,
)
from ..diagnostics import project_root
from ..settings import load_settings
from ..i18n import tr
from ..library_sources import IndexedAlbum
from ..models.song import Song
from ..icons import make_icon
from ..direct_album_lookup import is_prerelease_date
from ..local_track import local_duration_ms
from .formatting import localized_date


def _is_placeholder_title(title: str) -> bool:
    """True für Anbieter-Platzhalter wie „Track 2" (Vorabveröffentlichungen)."""
    return bool(re.fullmatch(r"track\s*\d+", str(title or "").strip().casefold()))
from ..player.preview import PreviewPlayer
from ..services.cover import load_cover
from ..providers.apple_music import (
    AppleAlbumCandidate,
)
from ..providers.apple_artist import (
    ArtistArtwork,
    fetch_artist_artwork,
)
from ..providers.theaudiodb import (
    EditorialInfo,
    fetch_album_info_with_apple_fallback,
    fetch_artist_info,
    information_language,
)
from ..media_library import tasks as _catalog_tasks
from ..media_library.tasks import (
    _fetch_discogs_hit_catalog,
    _fetch_live_artist_suggestions,
    _fetch_release_cover,
    _fetch_release_group_cover_with_discogs,
    _fetch_url_cover,
)
from ..media_library.presentation import (
    artist_text as _artist_text,
    category as _category,
    discogs_position as _discogs_position,
    duration as _duration,
    duration_ms as _duration_ms,
    label_artist_statistics as _label_artist_statistics,
    local_status_display as _local_status_display,
    merge_release_groups as _merge_release_groups,
    normalized as _normalized,
    release_source_details as _release_source_details,
    streaming_artist as _streaming_artist,
    track_title as _track_title,
    type_text as _type_text,
)
from ..media_library.streaming import (
    AvailabilityStatus,
    StreamingAvailability,
    StreamingAvailabilityCache,
    StreamingCheckReport,
    check_streaming_providers,
    streaming_release_key,
)
from ..secret_store import (
    SPOTIFY_CLIENT_SECRET,
    TIDAL_CLIENT_SECRET,
    get_secret,
)


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class Worker(QRunnable):
    def __init__(
        self,
        function,
        *args,
        **kwargs,
    ) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function(
                *self.args,
                **self.kwargs,
            )
        except Exception as error:
            self.signals.failed.emit(
                str(error)
            )
            return

        self.signals.finished.emit(
            result
        )


# Farbschema der Status-Chips (Text, Hintergrund) je lokalem Verfügbarkeits-
# Status. Farben funktionieren sowohl auf hellem als auch dunklem Theme.
_STATUS_CHIP_STYLES: dict[str, tuple[str, str, str]] = {
    "Lokal verfügbar": ("Lokal verfügbar", "#ffffff", "#2e7d32"),
    "Externe Quelle nicht erreichbar": (
        "Quelle nicht erreichbar",
        "#ffffff",
        "#b26a00",
    ),
    "Nicht vorhanden": ("Nicht vorhanden", "#ffffff", "#5f6368"),
    "Nein": ("Nicht vorhanden", "#ffffff", "#5f6368"),
}


# Eigene, hellere Punktfarben als die (dunklen) Chip-Hintergründe – der Punkt
# muss auf hellem Baumhintergrund gut sichtbar sein, während die Chips dunkel
# bleiben, damit ihr weißer Text lesbar ist.
_STATUS_DOT_COLORS: dict[str, str] = {
    "Lokal verfügbar": "#3ecf5a",
    "Externe Quelle nicht erreichbar": "#f0a33e",
    "Nicht vorhanden": "#9aa0a6",
    "Nein": "#9aa0a6",
}


def _status_dot_icon(status: str) -> QIcon:
    """Farbiger Statuspunkt (Ampel-Ersatz) – hell genug zum Erkennen."""
    color = _STATUS_DOT_COLORS.get(
        str(status or ""), _STATUS_DOT_COLORS["Nicht vorhanden"]
    )
    return make_icon("dot", color, size=16)


def _status_chip(status: str) -> tuple[str, str]:
    """Liefert (Beschriftung, Stylesheet) für den Status-Chip."""
    text, fg, bg = _STATUS_CHIP_STYLES.get(
        str(status or ""), _STATUS_CHIP_STYLES["Nicht vorhanden"]
    )
    style = (
        f"QLabel#localStatusChip {{ color: {fg}; background: {bg};"
        " border-radius: 8px; padding: 2px 10px; font-size: 11px;"
        " font-weight: 600; }}"
    )
    return text, style


def _resolve_deezer_previews(
    album: str,
    artist: str,
    expected_track_count: int,
) -> dict[str, str]:
    """Löst 30-Sekunden-Vorschauen über Deezer auf und ordnet sie nach
    normalisiertem Titel zu. Läuft im Worker-Thread; Fehler ergeben leere
    Zuordnung, damit die Trackliste nie blockiert wird."""
    from ..providers import deezer

    try:
        candidates = deezer.search_albums(
            album,
            artist,
            expected_track_count=expected_track_count,
        )
        best = next(
            (
                candidate
                for candidate in candidates
                if candidate.confidence >= deezer.MINIMUM_ALBUM_CONFIDENCE
            ),
            None,
        )

        if best is None:
            return {}

        result = deezer.lookup_album(best.album_id)
    except deezer.DeezerProviderError:
        return {}

    return _preview_map_from_tracks(result.tracks)


def _resolve_apple_previews(
    album: str,
    artist: str,
    expected_track_count: int,
    country: str,
) -> dict[str, str]:
    """Löst Vorschauen über Apple Music auf (Album finden → Lookup-Trackliste)."""
    from ..direct_album_lookup import (
        DirectAlbumLookupError,
        lookup_apple_album_by_id,
    )
    from ..providers.apple_music import (
        MINIMUM_ALBUM_CONFIDENCE,
        AppleMusicProviderError,
        search_album_variants,
    )

    try:
        candidates = search_album_variants(
            album,
            artist,
            expected_track_count=expected_track_count,
            country=country,
        )
    except AppleMusicProviderError:
        return {}

    best = next(
        (
            candidate
            for candidate in candidates
            if candidate.confidence >= MINIMUM_ALBUM_CONFIDENCE
        ),
        None,
    )

    if best is None:
        return {}

    try:
        result = lookup_apple_album_by_id(
            best.collection_id,
            country=best.country,
        )
    except DirectAlbumLookupError:
        return {}

    return _preview_map_from_tracks(result.tracks)


def _preview_title_key(title: str) -> str:
    """Normalisiert einen Titel für den Vorschau-Abgleich.

    Klammerzusätze und feat.-Angaben werden entfernt (Streaming-Titel wie
    "7Eleven (feat. Fatoni)" sollen zum lokalen "7Eleven" passen), danach
    bleiben nur Buchstaben/Ziffern. So bleibt die Zuordnung stabil, auch wenn
    Discogs-Positionen doppelte Tracknummern liefern.
    """
    text = str(title or "").lower()
    text = re.sub(r"[\(\[].*?[\)\]]", " ", text)
    text = re.sub(r"\b(feat|ft|featuring)\.?.*$", " ", text)
    return re.sub(r"[^a-z0-9]", "", text)


def _preview_map_from_tracks(tracks) -> dict[str, str]:
    """Ordnet Vorschau-URLs anhand des normalisierten Titels zu.

    Früher wurde nach (Disc, Tracknummer) zugeordnet; bei Discogs-Releases mit
    mehreren Medien/Seiten kollidieren diese Nummern jedoch (mehrfach „01“),
    wodurch die falsche Vorschau abgespielt wurde. Der Titel ist eindeutig.
    """
    mapping: dict[str, str] = {}

    for track in tracks:
        if not track.preview_url:
            continue

        key = _preview_title_key(getattr(track, "title", ""))

        if key and key not in mapping:
            mapping[key] = track.preview_url

    return mapping


class MediaLibraryWidget(QWidget):
    open_local_album = Signal(str)
    play_local_tracks = Signal(object, int)
    enqueue_local_tracks = Signal(object)

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(
            parent
        )
        self.thread_pool = QThreadPool(
            self
        )
        self.thread_pool.setMaxThreadCount(
            3
        )
        self.thumbnail_pool = QThreadPool(self)
        self.thumbnail_pool.setMaxThreadCount(4)
        self._workers: set[
            Worker
        ] = set()
        self.artists: list[
            ArtistCandidate
        ] = []
        self.result_items: list[
            tuple[
                str,
                object,
            ]
        ] = []
        self.release_groups: list[
            ReleaseGroup
        ] = []
        self.musicbrainz_release_groups: list[ReleaseGroup] = []
        self.artist_relations = []
        self.discogs_releases: list[DiscogsRelease] = []
        self.discogs_release_groups: list[ReleaseGroup] = []
        self.current_artist_name = ""
        self.current_artist_id = ""
        self.current_catalog_kind = ""
        self.current_artist_id = ""
        self.breadcrumbs: list[tuple[str, str, str]] = []
        self._preserve_breadcrumbs = False
        self.editions: list[
            Edition
        ] = []
        self.current_group: (
            ReleaseGroup
            | None
        ) = None
        self.current_tracks: list[Track] = []
        # 30-Sekunden-Track-Vorschau (Deezer). Eigener Player, damit die
        # lokale Wiedergabe-Queue unberührt bleibt.
        self.preview_player = PreviewPlayer(self)
        self.preview_player.state_changed.connect(
            self._on_preview_state
        )
        self.preview_player.error_occurred.connect(
            self._on_preview_error
        )
        self.track_preview_buttons: list[QPushButton] = []
        self.track_preview_urls: list[str] = []
        # Pro Zeile: liegt der Track lokal vor? Dann spielt der Knopf den
        # vollen Titel statt einer 30-Sekunden-Vorschau.
        self._row_is_local: list[bool] = []
        self._preview_token = 0
        # Zeilenindex der aktuell spielenden Vorschau (-1 = keine). Die
        # Hervorhebung erfolgt zeilen- statt urlbasiert, weil bei Mehrfach-
        # Discs dieselbe Vorschau-URL mehreren Zeilen zugeordnet sein kann.
        self._playing_preview_row = -1
        self._local_songs: list[Song] = []
        self.local_albums: dict[
            str,
            str
        ] = {}
        self.local_album_files: dict[
            str,
            str
        ] = {}
        self.local_album_status: dict[
            str,
            str
        ] = {}
        self.cover_cache_directory = (
            project_root()
            / "cache"
            / "media_library"
            / "covers"
        )
        self.cover_cache_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._cover_generation = 0
        self._current_cover_data: bytes | None = None
        self._category_icons = self._load_category_icons()
        self.ui_settings = QSettings("MusicTagStudio", "MusicTagStudio")
        self._streaming_results: dict[str, AppleAlbumCandidate | None] = {}
        self._provider_streaming_results: dict[
            str, dict[str, StreamingAvailability]
        ] = {}
        self._provider_streaming_errors: dict[str, dict[str, str]] = {}
        self._streaming_checked_at: dict[str, datetime] = {}
        self._editorial_request_key = ""
        self._editorial_heading = ""
        self._editorial_text = ""
        self._editorial_source_html = ""
        self.streaming_cache = StreamingAvailabilityCache()
        self.release_view_mode = str(self.ui_settings.value("media_library/view_mode", "discography"))
        self.cover_size_name = str(self.ui_settings.value("media_library/cover_size", "medium"))
        self._view_syncing = False
        self.language = load_settings().language
        self.catalog_controller = default_controller
        self.search_debug_lines: list[str] = []
        self._suggestion_query = ""
        self._suggestion_timer = QTimer(self)
        self._suggestion_timer.setSingleShot(True)
        self._suggestion_timer.setInterval(450)
        self._suggestion_timer.timeout.connect(self._request_live_suggestions)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(
            self
        )

        title = QLabel(
            "Medienbibliothek"
        )
        title.setStyleSheet(
            "font-size: 22px; font-weight: 600;"
        )
        root.addWidget(
            title
        )

        explanation = QLabel(
            "Künstler suchen, Veröffentlichungen und Editionen anzeigen "
            "und Tracklisten bei Bedarf laden. Streaming- und "
            "Qualitätsabfragen starten nur auf Knopfdruck."
        )
        explanation.setWordWrap(
            True
        )
        root.addWidget(
            explanation
        )

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("mediaSearchField")
        self.search_edit.setPlaceholderText(
            tr("search_artist_placeholder", self.language)
        )
        self.search_edit.returnPressed.connect(
            self.search
        )
        self.search_edit.textEdited.connect(
            self._schedule_live_suggestions
        )
        self.search_button = QPushButton(
            tr("search", self.language)
        )
        self.search_button.clicked.connect(
            self.search
        )
        search_row.addWidget(
            self.search_edit,
            stretch=1,
        )
        search_row.addWidget(
            self.search_button
        )
        self.discogs_refresh_button = QPushButton(
            "Discogs live aktualisieren"
        )
        self.discogs_refresh_button.setToolTip(
            "Ignoriert die lokale Discogs-Datenbank und lädt die "
            "Diskografie erneut über die API."
        )
        self.discogs_refresh_button.setEnabled(False)
        self.discogs_refresh_button.clicked.connect(
            self._refresh_discogs_live
        )
        search_row.addWidget(self.discogs_refresh_button)
        self.debug_button = QPushButton(
            "Debug"
        )
        self.debug_button.setCheckable(
            True
        )
        self.debug_button.toggled.connect(
            self._toggle_debug_panel
        )
        search_row.addWidget(
            self.debug_button
        )
        root.addLayout(
            search_row
        )

        self.live_suggestions = QListWidget()
        self.live_suggestions.setObjectName("liveSearchSuggestions")
        self.live_suggestions.setMaximumHeight(230)
        self.live_suggestions.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.live_suggestions.itemClicked.connect(
            self._live_suggestion_selected
        )
        self.live_suggestions.hide()
        root.addWidget(self.live_suggestions)

        self.breadcrumb_label = QLabel()
        self.breadcrumb_label.setTextFormat(Qt.TextFormat.RichText)
        self.breadcrumb_label.setOpenExternalLinks(False)
        self.breadcrumb_label.linkActivated.connect(
            self._breadcrumb_activated
        )
        self.breadcrumb_label.setStyleSheet(
            "padding: 3px 0; color: palette(mid);"
        )
        self.breadcrumb_label.hide()
        root.addWidget(self.breadcrumb_label)

        self.suggestion_label = QLabel()
        self.suggestion_label.setWordWrap(
            True
        )
        self.suggestion_label.setOpenExternalLinks(
            False
        )
        self.suggestion_label.linkActivated.connect(
            self._use_artist_suggestion
        )
        self.suggestion_label.hide()
        root.addWidget(
            self.suggestion_label
        )

        self.debug_output = QTextEdit()
        self.debug_output.setReadOnly(
            True
        )
        self.debug_output.setMaximumHeight(
            180
        )
        self.debug_output.setPlaceholderText(
            "Hier erscheinen MusicBrainz-Anfragen, "
            "HTTP-Status und Trefferzahlen."
        )
        self.debug_output.hide()
        root.addWidget(
            self.debug_output
        )

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        artist_panel = QWidget()
        artist_layout = QVBoxLayout(
            artist_panel
        )
        artist_layout.addWidget(
            QLabel(
                tr("search_results", self.language)
            )
        )
        self.artist_list = QListWidget()
        self.artist_list.currentRowChanged.connect(
            self._artist_selected
        )
        artist_layout.addWidget(
            self.artist_list,
            stretch=2,
        )
        artist_layout.addWidget(QLabel("Verknüpfungen"))
        self.relations_tree = QTreeWidget()
        self.relations_tree.setHeaderHidden(True)
        self.relations_tree.setRootIsDecorated(True)
        self.relations_tree.setToolTip(
            "Ein Klick auf einen Künstler öffnet dessen Diskografie."
        )
        self.relations_tree.itemClicked.connect(self._relation_clicked)
        artist_layout.addWidget(self.relations_tree, stretch=1)

        group_panel = QWidget()
        group_layout = QVBoxLayout(group_panel)
        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("Veröffentlichungen"))
        view_row.addStretch()
        view_row.addWidget(QLabel("Ansicht:"))
        self.view_mode_combo = QComboBox()
        for label, value in (("Discografie", "discography"), ("Tabelle", "table"), ("Coverraster", "covers"), ("Cover + Liste", "cover_list")):
            self.view_mode_combo.addItem(label, value)
        self.view_mode_combo.currentIndexChanged.connect(self._view_mode_changed)
        view_row.addWidget(self.view_mode_combo)
        view_row.addWidget(QLabel("Covergröße:"))
        self.cover_size_combo = QComboBox()
        for label, value in (("Klein", "small"), ("Mittel", "medium"), ("Groß", "large"), ("Sehr groß", "xlarge")):
            self.cover_size_combo.addItem(label, value)
        self.cover_size_combo.currentIndexChanged.connect(self._cover_size_changed)
        view_row.addWidget(self.cover_size_combo)
        group_layout.addLayout(view_row)
        self.release_view_stack = QStackedWidget()
        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderLabels(["Veröffentlichung", "Jahr", "Kategorie", "Quelle", "Status"])
        self.group_tree.setIconSize(QSize(18,18)); self.group_tree.setIndentation(22); self.group_tree.setColumnCount(5)
        self.group_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.group_tree.currentItemChanged.connect(self._group_selected)
        self.group_tree.header().sectionClicked.connect(
            self._sort_discography_column
        )
        self._discography_sort_column = 1
        self._discography_sort_ascending = True
        self.release_view_stack.addWidget(self.group_tree)
        self.release_table = QTableWidget(0,7)
        self.release_table.setHorizontalHeaderLabels(["Titel","Künstler","Jahr","Kategorie","Quelle","Label / Format","Status"])
        self.release_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.release_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.release_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.release_table.setSortingEnabled(True)
        self.release_table.currentCellChanged.connect(self._table_release_selected)
        self.release_view_stack.addWidget(self.release_table)
        self.cover_model = QStandardItemModel(self)
        self.cover_view = QListView(); self.cover_view.setModel(self.cover_model)
        self.cover_view.setViewMode(QListView.ViewMode.IconMode); self.cover_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.cover_view.setMovement(QListView.Movement.Static); self.cover_view.setWrapping(True)
        self.cover_view.clicked.connect(self._cover_release_selected)
        self.release_view_stack.addWidget(self.cover_view)
        self.cover_list = QListWidget(); self.cover_list.currentRowChanged.connect(self._cover_list_release_selected)
        self.release_view_stack.addWidget(self.cover_list)
        group_layout.addWidget(self.release_view_stack)
        self.view_mode_combo.setCurrentIndex(max(0, self.view_mode_combo.findData(self.release_view_mode)))
        self.cover_size_combo.setCurrentIndex(max(0, self.cover_size_combo.findData(self.cover_size_name)))
        self._apply_cover_size()

        detail_panel = QWidget()
        detail_panel_layout = QVBoxLayout(detail_panel)
        detail_panel_layout.setContentsMargins(0, 0, 0, 0)
        metadata_panel = QWidget()
        detail_layout = QVBoxLayout(metadata_panel)
        detail_layout.setContentsMargins(0, 0, 4, 0)
        detail_layout.setSpacing(6)
        detail_header = QHBoxLayout()
        self.cover_label = QLabel(
            "Kein Cover verfügbar"
        )
        self.cover_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.cover_label.setFixedSize(
            170,
            170,
        )
        self.cover_label.setStyleSheet(
            "border: 1px solid #3a3a3a; background: #171717;"
        )
        self.cover_label.setToolTip(
            "Cover der aktuell gewählten Edition"
        )
        detail_header.addWidget(
            self.cover_label
        )

        detail_text = QVBoxLayout()
        detail_text.setSpacing(2)
        self.group_title = QLabel(
            "Keine Veröffentlichung ausgewählt"
        )
        self.group_title.setWordWrap(
            True
        )
        self.group_title.setStyleSheet(
            "font-size: 18px; font-weight: 600;"
        )
        detail_text.addWidget(
            self.group_title
        )

        # Status-Chip (Pille) statt Fließtext für die lokale Verfügbarkeit.
        self.local_status_chip = QLabel("")
        self.local_status_chip.setObjectName("localStatusChip")
        # Chip für Vorabveröffentlichungen (nur bei tagesgenauem Zukunftsdatum
        # aus der Apple-Streaming-Prüfung).
        self.prerelease_chip = QLabel("")
        self.prerelease_chip.setObjectName("prereleaseChip")
        self.prerelease_chip.hide()
        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip_row.addWidget(self.local_status_chip)
        chip_row.addWidget(self.prerelease_chip)
        chip_row.addStretch()
        detail_text.addLayout(chip_row)

        self.group_meta = QLabel("")
        self.group_meta.setWordWrap(
            True
        )
        detail_text.addWidget(
            self.group_meta
        )

        self.source_details = QLabel("")
        self.source_details.setObjectName("releaseSourceDetails")
        self.source_details.setWordWrap(True)
        self.source_details.setTextFormat(Qt.TextFormat.RichText)
        self.source_details.setMinimumHeight(72)
        self.source_details.setMaximumHeight(96)
        self.source_details.setStyleSheet(
            "QLabel#releaseSourceDetails {"
            "background: palette(alternate-base);"
            "border: 1px solid palette(mid);"
            "border-radius: 10px; padding: 4px 8px;"
            "}"
        )
        self.source_details.hide()
        detail_text.addWidget(self.source_details)
        detail_text.addStretch()
        detail_header.addLayout(
            detail_text,
            stretch=1,
        )
        detail_layout.addLayout(
            detail_header
        )

        self.streaming_button = QPushButton(
            "Streaming prüfen"
        )
        self.streaming_button.clicked.connect(
            self.check_streaming
        )
        self.streaming_button.setEnabled(
            False
        )
        self.quality_button = QPushButton(
            "Qualität prüfen"
        )
        self.quality_button.clicked.connect(
            self.check_quality
        )
        self.quality_button.setEnabled(
            False
        )
        self.apple_button = QPushButton(
            "Apple Music"
        )
        self.apple_button.setEnabled(
            False
        )
        self.apple_button.clicked.connect(
            self.open_apple
        )
        self.tidal_button = QPushButton("TIDAL")
        self.tidal_button.setEnabled(False)
        self.tidal_button.clicked.connect(
            lambda: self._open_streaming_provider(self.tidal_button)
        )
        self.spotify_button = QPushButton("Spotify")
        self.spotify_button.setEnabled(False)
        self.spotify_button.clicked.connect(
            lambda: self._open_streaming_provider(self.spotify_button)
        )
        # Gruppe "Prüfen": Streaming-/Qualitätsabfragen.
        check_group = QGroupBox("Prüfen")
        check_layout = QHBoxLayout(check_group)
        check_layout.setContentsMargins(8, 4, 8, 8)
        check_layout.addWidget(self.streaming_button)
        check_layout.addWidget(self.quality_button)
        detail_layout.addWidget(check_group)

        # Gruppe "Auf Dienst öffnen": Album beim jeweiligen Anbieter aufrufen.
        service_group = QGroupBox("Auf Dienst öffnen")
        service_layout = QHBoxLayout(service_group)
        service_layout.setContentsMargins(8, 4, 8, 8)
        service_layout.addWidget(self.apple_button)
        service_layout.addWidget(self.tidal_button)
        service_layout.addWidget(self.spotify_button)
        detail_layout.addWidget(service_group)

        self.streaming_status = QLabel(
            "Streaming und Qualität wurden nicht abgefragt."
        )
        self.streaming_status.setWordWrap(
            True
        )
        detail_layout.addWidget(
            self.streaming_status
        )

        self.editorial_info = QTextBrowser()
        self.editorial_info.setObjectName("editorialInfo")
        self.editorial_info.setOpenExternalLinks(True)
        self.editorial_info.setMinimumHeight(82)
        self.editorial_info.setMaximumHeight(112)
        self.editorial_info.setStyleSheet(
            "QTextBrowser#editorialInfo {"
            "background: palette(alternate-base);"
            "border: 1px solid palette(mid);"
            "border-radius: 10px; padding: 5px;"
            "}"
        )
        self.editorial_info.hide()
        detail_layout.addWidget(self.editorial_info)
        self.editorial_more_button = QPushButton("Mehr anzeigen …")
        self.editorial_more_button.clicked.connect(
            self._show_full_editorial
        )
        self.editorial_more_button.hide()
        detail_layout.addWidget(
            self.editorial_more_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        edition_form = QFormLayout()
        self.edition_combo = QComboBox()
        self.edition_combo.currentIndexChanged.connect(
            self._edition_selected
        )
        edition_form.addRow(
            "Edition:",
            self.edition_combo,
        )
        self.edition_details = QLabel("")
        self.edition_details.setWordWrap(
            True
        )
        edition_form.addRow(
            "Eckdaten:",
            self.edition_details,
        )
        detail_layout.addLayout(
            edition_form
        )

        self.open_local_button = QPushButton(
            "Lokales Album im Tagger öffnen"
        )
        self.open_local_button.setEnabled(
            False
        )
        self.open_local_button.clicked.connect(
            self._open_local
        )
        self.enqueue_local_button = QPushButton(
            "Zur Warteschlange"
        )
        self.enqueue_local_button.setEnabled(False)
        self.enqueue_local_button.clicked.connect(
            self._enqueue_local_album
        )
        # Gruppe "Lokal": Aktionen für die lokal vorhandene Kopie.
        local_group = QGroupBox("Lokal")
        local_actions = QHBoxLayout(local_group)
        local_actions.setContentsMargins(8, 4, 8, 8)
        local_actions.addWidget(self.open_local_button, 1)
        local_actions.addWidget(self.enqueue_local_button)
        detail_layout.addWidget(local_group)

        metadata_scroll = QScrollArea()
        metadata_scroll.setObjectName("releaseMetadataScroll")
        metadata_scroll.setWidgetResizable(True)
        metadata_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        metadata_scroll.setWidget(metadata_panel)

        track_panel = QWidget()
        self.track_panel = track_panel
        track_layout = QVBoxLayout(track_panel)
        track_layout.setContentsMargins(0, 4, 0, 0)
        track_layout.setSpacing(4)
        track_layout.addWidget(QLabel("Trackliste"))
        self.track_table = QTableWidget(
            0,
            5,
        )
        self.track_table.setHorizontalHeaderLabels(
            [
                "CD",
                "Track",
                "Titel",
                "Dauer",
                "Wiedergabe",
            ]
        )
        self.track_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.track_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.track_table.cellDoubleClicked.connect(
            self._play_local_track
        )
        self.track_table.setMinimumHeight(190)
        track_layout.addWidget(
            self.track_table,
            stretch=1,
        )

        self.detail_splitter = QSplitter(Qt.Orientation.Vertical)
        self.detail_splitter.setChildrenCollapsible(False)
        self.detail_splitter.addWidget(metadata_scroll)
        self.detail_splitter.addWidget(track_panel)
        self.detail_splitter.setStretchFactor(0, 0)
        self.detail_splitter.setStretchFactor(1, 1)
        saved_detail_sizes = self.ui_settings.value(
            "media_library/detail_splitter_sizes",
            [390, 260],
        )
        try:
            detail_sizes = [int(value) for value in saved_detail_sizes]
        except (TypeError, ValueError):
            detail_sizes = [390, 260]
        self.detail_splitter.setSizes(
            detail_sizes if len(detail_sizes) == 2 else [390, 260]
        )
        self.detail_splitter.splitterMoved.connect(
            lambda *_args: self.ui_settings.setValue(
                "media_library/detail_splitter_sizes",
                self.detail_splitter.sizes(),
            )
        )
        detail_panel_layout.addWidget(self.detail_splitter)

        splitter.addWidget(
            artist_panel
        )
        splitter.addWidget(
            group_panel
        )
        splitter.addWidget(
            detail_panel
        )
        splitter.setSizes(
            [
                230,
                430,
                770,
            ]
        )
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)
        root.addWidget(
            splitter,
            stretch=1,
        )

    def set_library_index(
        self,
        albums: list[IndexedAlbum],
    ) -> None:
        folders: dict[str, str] = {}
        files: dict[str, str] = {}
        statuses: dict[str, str] = {}

        for album in albums:
            key = _normalized(
                album.album
            )

            if not key:
                continue

            current = statuses.get(
                key
            )

            if album.source_online:
                folders[key] = album.folder
                files[key] = (
                    album.representative_file
                )
                statuses[key] = (
                    "Lokal verfügbar"
                )
            elif current is None:
                folders[key] = album.folder
                files[key] = (
                    album.representative_file
                )
                statuses[key] = (
                    "Externe Quelle nicht erreichbar"
                )

        self.local_albums = folders
        self.local_album_files = files
        self.local_album_status = statuses
        self._refresh_local_markers()

    def set_local_songs(
        self,
        songs: list[Song],
    ) -> None:
        self._local_songs = list(songs)
        albums: dict[
            str,
            str
        ] = {}
        album_files: dict[
            str,
            str
        ] = {}

        for song in songs:
            key = _normalized(
                song.album
            )

            if (
                key
                and key not in albums
            ):
                albums[key] = str(
                    Path(
                        song.path
                    ).parent
                )
                album_files[key] = (
                    song.path
                )

        self.local_albums = albums
        self.local_album_files = (
            album_files
        )
        self.local_album_status = {
            key: "Lokal verfügbar"
            for key in albums
        }
        self._refresh_local_markers()

    def _match_local_index(self, track, songs: list[Song]) -> int:
        """Findet den Index der lokalen Datei zu einem Albumtrack (oder -1).

        Der Titel wird zuerst geprüft: Die angezeigte Veröffentlichung (z. B.
        eine Single) kann eine andere Tracknummerierung haben als der lokale
        Ordner (z. B. das ganze Album). Ein reiner Nummern-Abgleich würde dann
        die falsche Datei treffen. Die Tracknummer dient nur noch als Fallback.
        """
        wanted_title = _normalized(track.title)
        start_index = next(
            (
                index
                for index, song in enumerate(songs)
                if wanted_title and _normalized(song.title) == wanted_title
            ),
            -1,
        )

        if start_index < 0:
            start_index = next(
                (
                    index
                    for index, song in enumerate(songs)
                    if (
                        _tag_number(song.disc) == int(track.disc_number or 0)
                        and _tag_number(song.track)
                        == int(track.track_number or 0)
                    )
                ),
                -1,
            )

        return start_index

    def _local_playback_for_row(self, row: int) -> tuple[list[Song], int]:
        """Liefert (Wiedergabeliste, Startindex) oder ([], -1).

        Die Liste enthält nur die lokal vorhandenen Titel der *angezeigten*
        Trackliste (in deren Reihenfolge). So landen keine ordner-fremden
        Dateien in der Warteschlange – etwa andere Album-Titel, die im selben
        lokalen Ordner liegen wie eine Single.
        """
        if not (0 <= row < len(self.current_tracks)) or self.current_group is None:
            return [], -1

        album_songs = self._current_local_album_songs()

        if not album_songs:
            return [], -1

        playlist: list[Song] = []
        start_index = -1
        for track_row, track in enumerate(self.current_tracks):
            match = self._match_local_index(track, album_songs)
            if match < 0:
                continue
            if track_row == row:
                start_index = len(playlist)
            playlist.append(album_songs[match])

        if not playlist:
            return [], -1

        return playlist, start_index

    def _play_local_track(self, row: int, _column: int) -> None:
        if not (0 <= row < len(self.current_tracks)):
            return
        if self.current_group is None:
            return

        songs, start_index = self._local_playback_for_row(row)

        if not songs:
            self._set_status(
                "Die lokalen Albumdateien sind noch nicht eingelesen. "
                "Bitte zuerst die Bibliotheksdaten aktualisieren."
            )
            return

        if start_index < 0:
            self._set_status(
                "Der ausgewählte Titel konnte keiner lokalen Datei "
                "zugeordnet werden."
            )
            return

        self.play_local_tracks.emit(songs, start_index)

    def _current_local_album_songs(self) -> list[Song]:
        group = self.current_group
        if group is None:
            return []
        album_key = _normalized(group.title)
        songs = [
            song
            for song in self._local_songs
            if _normalized(song.album) == album_key
            and Path(song.path).is_file()
        ]
        artist_key = _normalized(self.current_artist_name)
        artist_songs = [
            song
            for song in songs
            if artist_key in {
                _normalized(song.album_artist),
                _normalized(song.artist),
            }
        ]
        if artist_songs:
            songs = artist_songs
        songs.sort(key=lambda song: (
            _tag_number(song.disc),
            _tag_number(song.track),
            _normalized(song.title),
        ))
        return songs

    def _enqueue_local_album(self) -> None:
        songs = self._current_local_album_songs()
        if not songs:
            self._set_status(
                "Für dieses Album wurden keine erreichbaren lokalen Titel gefunden."
            )
            return
        self.enqueue_local_tracks.emit(songs)

    def highlight_playing_song(self, song: Song) -> None:
        group = self.current_group
        if (
            group is None
            or _normalized(song.album) != _normalized(group.title)
        ):
            return
        disc = _tag_number(song.disc)
        number = _tag_number(song.track)
        title = _normalized(song.title)
        row = next(
            (
                index
                for index, track in enumerate(self.current_tracks)
                if (
                    int(track.disc_number or 0) == disc
                    and int(track.track_number or 0) == number
                )
            ),
            -1,
        )
        if row < 0:
            row = next(
                (
                    index
                    for index, track in enumerate(self.current_tracks)
                    if _normalized(track.title) == title
                ),
                -1,
            )
        if row >= 0:
            self.track_table.selectRow(row)
            item = self.track_table.item(row, 0)
            if item is not None:
                self.track_table.scrollToItem(item)

    def search_artist(
        self,
        artist_name: str,
        *,
        preserve_breadcrumbs: bool = False,
    ) -> None:
        artist_name = str(
            artist_name or ""
        ).strip()

        if not artist_name:
            return

        self.search_edit.setText(
            artist_name
        )
        self._preserve_breadcrumbs = preserve_breadcrumbs
        self.search()

    def search(self) -> None:
        query = self.search_edit.text().strip()

        if not query:
            return

        self._suggestion_timer.stop()
        self.live_suggestions.hide()

        self.current_catalog_kind = ""

        if not self._preserve_breadcrumbs:
            self.breadcrumbs = []
            self._render_breadcrumbs()
        self._preserve_breadcrumbs = False

        self.search_button.setEnabled(
            False
        )
        self.artist_list.clear()
        self.suggestion_label.clear()
        self.suggestion_label.hide()
        self.group_tree.clear()
        self.relations_tree.clear()
        self.release_table.setRowCount(
            0
        )
        self.cover_model.clear()
        self.cover_list.clear()
        self.edition_combo.clear()
        self.edition_details.clear()
        self.source_details.clear()
        self.source_details.hide()
        self._editorial_request_key = ""
        self.editorial_info.clear()
        self.editorial_info.hide()
        self.editorial_more_button.hide()
        self.track_table.setRowCount(
            0
        )
        self.open_local_button.setProperty("local_path", "")
        self.open_local_button.setEnabled(False)
        self.enqueue_local_button.setEnabled(False)
        self.local_status_chip.clear()
        self.local_status_chip.setStyleSheet("")
        self.prerelease_chip.hide()
        self.prerelease_chip.clear()
        self._show_cover(None)
        self.group_title.setText(
            tr("search_running", self.language)
        )
        self._set_status(
            tr("artist_search", self.language, query=query)
        )
        self.search_debug_lines = [
            f"Suche: {query}"
        ]
        self._refresh_debug_output()
        self._run(
            self.catalog_controller.search_artists,
            query,
            preferred_country=load_settings().apple_country,
            finished=self._artists_loaded,
        )

    def _schedule_live_suggestions(self, text: str) -> None:
        query = str(text or "").strip()
        self._suggestion_timer.stop()
        self._suggestion_query = query
        if len(query) < 3:
            self.live_suggestions.clear()
            self.live_suggestions.hide()
            return
        self._suggestion_timer.start()

    def _request_live_suggestions(self) -> None:
        query = self._suggestion_query
        if len(query) < 3:
            return
        self._run(
            _fetch_live_artist_suggestions,
            self.catalog_controller,
            query,
            finished=lambda result, wanted=query: self._show_live_suggestions(
                wanted, result
            ),
            failed=lambda _message: self.live_suggestions.hide(),
        )

    def _show_live_suggestions(self, query: str, result) -> None:
        if query != self.search_edit.text().strip():
            return
        artists = list(result or ())
        self.live_suggestions.clear()
        for suggestion in artists:
            artist_name = str(getattr(suggestion, "name", suggestion))
            correction = bool(getattr(suggestion, "correction", False))
            label = (
                f"Meintest du: {artist_name}?"
                if correction
                else artist_name
            )
            item = QListWidgetItem(f"⌕  {label}")
            item.setData(Qt.ItemDataRole.UserRole, artist_name)
            self.live_suggestions.addItem(item)
        self.live_suggestions.setVisible(bool(artists))

    def _live_suggestion_selected(self, item: QListWidgetItem) -> None:
        artist_name = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not artist_name:
            return
        self.live_suggestions.hide()
        self.search_artist(artist_name)

    def _artists_loaded(
        self,
        result,
    ) -> None:
        if isinstance(
            result,
            ArtistSearchResponse,
        ):
            self.artists = list(
                result.artists
            )
            used_fuzzy_search = (
                result.suggestion_mode
            )
            for trace in result.traces:
                self.search_debug_lines.append(
                    trace.as_text()
                )
        elif isinstance(
            result,
            ArtistSearchResult,
        ):
            self.artists = list(
                result.artists
            )
            used_fuzzy_search = (
                result.used_fuzzy_search
            )
        else:
            self.artists = list(
                result
            )
            used_fuzzy_search = False

        self._refresh_debug_output()
        self.result_items = []
        self.artist_list.clear()

        for artist in self.artists:
            item = QListWidgetItem(
                _artist_text(
                    artist
                )
            )
            item.setToolTip(
                artist.disambiguation
                or artist.country
            )
            self.artist_list.addItem(
                item
            )
            self.result_items.append(
                (
                    "musicbrainz_artist",
                    artist,
                )
            )

        self.search_button.setEnabled(
            True
        )

        if not self.artists:
            self.suggestion_label.hide()
            settings = load_settings()
            if settings.discogs_token.strip():
                self.group_title.setText("Discogs wird durchsucht …")
                self.group_meta.setText(
                    "MusicBrainz lieferte keinen Künstler. Suche nach "
                    "exakten Künstlern, Labels und Veröffentlichungen bei Discogs."
                )
                self._set_status("Exakte Discogs-Katalogsuche läuft …")
                self._run(
                    _search_exact_discogs_catalog,
                    self.search_edit.text().strip(),
                    settings.discogs_token,
                    finished=self._exact_catalog_loaded,
                )
            else:
                self._show_no_catalog_results()
            return

        self._set_status(
            tr(
                "artists_found",
                self.language,
                count=len(
                    self.artists
                ),
            )
        )

        if used_fuzzy_search:
            links = []
            for index, artist in enumerate(
                self.artists[:5]
            ):
                links.append(
                    (
                        f'<a href="artist:{index}">'
                        f"{html.escape(artist.name)}"
                        "</a>"
                    )
                )
            self.suggestion_label.setText(
                (
                    "Kein exakter Treffer. "
                    "Meintest du vielleicht: "
                    + ", ".join(
                        links
                    )
                    + "?"
                )
            )
            self.suggestion_label.show()
        else:
            self.suggestion_label.hide()

        self.artist_list.setCurrentRow(
            0
        )

    def _show_no_catalog_results(self) -> None:
        self.group_title.setText("Keine Treffer gefunden")
        self.group_meta.setText(
            "Weder MusicBrainz noch der aktivierte Katalog lieferten "
            "einen exakten Treffer."
        )
        self._set_status("Keine Künstler, Labels oder Veröffentlichungen gefunden.")

    def _exact_catalog_loaded(self, hits) -> None:
        if hits:
            self._catalog_loaded(hits)
        else:
            self.search_button.setEnabled(True)
            self._show_no_catalog_results()

    def _use_artist_suggestion(
        self,
        link: str,
    ) -> None:
        if not link.startswith(
            "artist:"
        ):
            return

        try:
            index = int(
                link.split(
                    ":",
                    1,
                )[1]
            )
            artist = self.artists[
                index
            ]
        except (
            ValueError,
            IndexError,
            TypeError,
        ):
            return

        self.search_edit.setText(
            artist.name
        )
        self.suggestion_label.hide()
        self.search()

    def _toggle_debug_panel(
        self,
        visible: bool,
    ) -> None:
        self.debug_output.setVisible(
            visible
        )
        if visible:
            self._refresh_debug_output()

    def _refresh_debug_output(
        self,
    ) -> None:
        self.debug_output.setPlainText(
            "\n\n".join(
                self.search_debug_lines
            )
        )

    def _catalog_loaded(
        self,
        hits,
    ) -> None:
        self.catalog_hits = list(
            hits
        )
        self.artists = []
        self.result_items = []
        self.artist_list.clear()
        kind_labels = {
            "artist": "Künstler",
            "release": "Veröffentlichung",
            "master": "Veröffentlichung",
            "label": "Label",
        }

        for hit in self.catalog_hits:
            prefix = kind_labels.get(
                hit.kind,
                hit.kind,
            )
            subtitle = (
                f"\n{hit.subtitle}"
                if hit.subtitle
                else ""
            )
            item = QListWidgetItem(
                f"{prefix}: {hit.title}{subtitle}"
            )
            item.setToolTip(
                hit.external_url
            )
            self.artist_list.addItem(
                item
            )
            self.result_items.append(
                (
                    f"discogs_{hit.kind}",
                    hit,
                )
            )

        self.search_button.setEnabled(
            True
        )
        self._set_status(
            f"{len(self.catalog_hits)} Katalogtreffer gefunden."
        )

        if self.catalog_hits:
            self.artist_list.setCurrentRow(
                0
            )

    def _artist_selected(
        self,
        row: int,
    ) -> None:
        if (
            row < 0
            or row >= len(
                self.result_items
            )
        ):
            return

        result_type, artist = self.result_items[
            row
        ]

        if result_type.startswith("discogs_"):
            self._discogs_result_selected(result_type, artist)
            return

        if result_type != "musicbrainz_artist":
            return

        self.release_groups = []
        self.current_group = None
        self.track_panel.hide()
        self.musicbrainz_release_groups = []
        self.discogs_release_groups = []
        self.current_artist_name = artist.name
        self.current_artist_id = artist.artist_id
        self.current_catalog_kind = "artist"
        self._push_breadcrumb(
            "artist",
            artist.name,
            artist.artist_id,
        )
        self.group_tree.clear()
        self.release_table.setRowCount(
            0
        )
        self.cover_model.clear()
        self.cover_list.clear()
        self.edition_combo.clear()
        self.track_table.setRowCount(
            0
        )
        self._cover_generation += 1
        self._show_cover(
            None
        )
        self.cover_label.setText("Künstlerbild wird geladen …")
        settings = load_settings()
        self._run(
            fetch_artist_artwork,
            artist.name,
            settings.apple_country,
            self.language,
            self.cover_cache_directory,
            settings.discogs_token,
            finished=self._artist_artwork_loaded,
            transform=lambda artwork, artist_id=artist.artist_id: (
                artist_id,
                artwork,
            ),
            failed=lambda _message: self._artist_artwork_failed(
                artist.artist_id
            ),
        )
        self.group_title.setText(
            artist.name
        )
        self.group_meta.setText(
            "MusicBrainz-Künstler"
        )
        self._request_editorial(
            f"artist:{artist.artist_id}",
            "artist",
            fetch_artist_info,
            artist.name,
            self.language,
        )
        self.relations_tree.clear()
        loading_item = QTreeWidgetItem(["Verknüpfungen werden geladen …"])
        self.relations_tree.addTopLevelItem(loading_item)
        self._run(
            self.catalog_controller.load_artist_relations,
            artist.artist_id,
            finished=self._relations_loaded,
        )
        self._set_status(
            f"Veröffentlichungen von {artist.name} werden geladen …"
        )
        self.search_debug_lines.append(
            f"Veröffentlichungen laden: {artist.name}"
        )
        self._refresh_debug_output()
        self._run(
            self.catalog_controller.load_release_groups,
            artist.artist_id,
            finished=self._groups_loaded,
        )
        settings = load_settings()
        self.discogs_refresh_button.setEnabled(
            bool(settings.discogs_token.strip())
        )
        if settings.discogs_token.strip():
            self._set_status(
                f"Veröffentlichungen von {artist.name} werden aus MusicBrainz und Discogs geladen …"
            )
            self._run(
                _fetch_discogs_catalog,
                artist.name,
                settings.discogs_token,
                finished=self._discogs_catalog_releases_loaded,
            )

    def _discogs_result_selected(
        self,
        result_type: str,
        hit: DiscogsCatalogHit,
    ) -> None:
        settings = load_settings()
        if not settings.discogs_token.strip():
            return
        self.release_groups = []
        self.musicbrainz_release_groups = []
        self.discogs_release_groups = []
        self.current_artist_name = hit.title
        self.current_artist_id = ""
        self.current_catalog_kind = hit.kind
        self.group_tree.clear()
        self.release_table.setRowCount(0)
        self.cover_model.clear()
        self.cover_list.clear()
        self.relations_tree.clear()
        self.edition_combo.clear()
        self.track_table.setRowCount(0)
        self._show_cover(None)
        self.group_title.setText(hit.title)
        self.group_meta.setText(
            "Discogs-Label" if hit.kind == "label" else "Discogs-Katalogtreffer"
        )
        self._push_breadcrumb(hit.kind, hit.title, str(hit.entity_id))
        self.discogs_refresh_button.setEnabled(hit.kind in {"artist", "label"})
        self._set_status(f"{hit.title} wird aus Discogs geladen …")
        if hit.kind in {"artist", "label"}:
            self._run(
                _fetch_discogs_hit_catalog,
                hit,
                self.search_edit.text().strip(),
                settings.discogs_token,
                finished=self._discogs_catalog_releases_loaded,
            )
        else:
            self._run(
                fetch_catalog_release,
                hit.kind,
                hit.entity_id,
                settings.discogs_token,
                finished=self._single_discogs_release_loaded,
            )

    def _relations_loaded(self, result) -> None:
        if (
            isinstance(result, ArtistRelationsResponse)
            and result.artist_id != self.current_artist_id
        ):
            return
        self.relations_tree.clear()
        if isinstance(result, ArtistRelationsResponse):
            self.artist_relations = list(result.relations)
            for trace in result.traces:
                self.search_debug_lines.append(trace.as_text())
        else:
            self.artist_relations = list(result or [])
        self._refresh_debug_output()

        if not self.artist_relations:
            self.relations_tree.addTopLevelItem(
                QTreeWidgetItem(["Keine Verknüpfungen gefunden"])
            )
            return

        groups: dict[str, list] = {}
        for relation in self.artist_relations:
            groups.setdefault(self._relation_category(relation), []).append(relation)

        order = (
            "Künstleridentitäten", "Person", "Mitglieder", "Gruppen",
            "Kollaborationen", "Namensvarianten",
            "Produzenten / Mitwirkende", "Labels", "Weitere",
        )
        for category in order:
            entries = groups.get(category, [])
            if not entries:
                continue
            parent = QTreeWidgetItem([f"{category} ({len(entries)})"])
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            self.relations_tree.addTopLevelItem(parent)
            for relation in entries:
                suffix = " (ehemalig)" if relation.ended else ""
                role = self._relation_role_text(relation)
                role_suffix = f" · {role}" if role else ""
                child = QTreeWidgetItem(
                    [f"{relation.name}{role_suffix}{suffix}"]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, relation)
                details = [relation.relation_type]
                if relation.disambiguation:
                    details.append(relation.disambiguation)
                if relation.attributes:
                    details.append(", ".join(relation.attributes))
                if relation.begin or relation.end:
                    details.append(f"{relation.begin or '?'}–{relation.end or 'heute'}")
                child.setToolTip(0, " · ".join(details))
                parent.addChild(child)
        self.relations_tree.expandAll()

    @staticmethod
    def _relation_category(relation) -> str:
        relation_type = relation.relation_type.casefold()
        if relation.target_type == "label":
            return "Labels"
        if relation_type in {"member of band", "founder"}:
            return "Gruppen" if relation.direction == "forward" else "Mitglieder"
        if relation_type in {"is person", "performance name"}:
            return "Künstleridentitäten" if relation.direction == "forward" else "Person"
        if "alias" in relation_type:
            return "Namensvarianten"
        if any(word in relation_type for word in ("producer", "mix", "master", "engineer", "instrument", "vocal")):
            return "Produzenten / Mitwirkende"
        if any(word in relation_type for word in ("collaboration", "collaborated", "supporting musician")):
            return "Kollaborationen"
        return "Weitere"

    @staticmethod
    def _relation_role_text(relation) -> str:
        relation_type = relation.relation_type.casefold()
        if relation_type == "is person":
            return "Künstleridentität" if relation.direction == "forward" else "bürgerliche Person"
        if relation_type == "performance name":
            return "Künstlername"
        if relation_type in {"member of band", "founder"} and relation.attributes:
            return ", ".join(relation.attributes)
        return ""

    def _relation_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        relation = item.data(0, Qt.ItemDataRole.UserRole)
        if relation is None:
            return
        if (
            isinstance(relation, tuple)
            and len(relation) == 2
            and relation[0] == "label_artist"
        ):
            self.search_artist(
                relation[1],
                preserve_breadcrumbs=True,
            )
            return
        if relation.target_type in {"artist", "alias"}:
            self._open_related_artist(relation)
        elif relation.target_type == "label":
            self._set_status(
                f"MusicBrainz-Label „{relation.name}“ wird geöffnet …"
            )
            webbrowser.open(
                f"https://musicbrainz.org/label/{relation.target_id}"
            )

    def _open_related_artist(self, relation) -> None:
        artist = ArtistCandidate(
            artist_id=relation.target_id,
            name=relation.name,
            disambiguation=relation.disambiguation,
        )
        self.search_edit.setText(relation.name)
        self.artists = [artist]
        self.result_items = [("musicbrainz_artist", artist)]
        self.artist_list.clear()
        item = QListWidgetItem(_artist_text(artist))
        item.setToolTip(relation.disambiguation)
        self.artist_list.addItem(item)
        self.artist_list.setCurrentRow(0)

    def _render_discogs_label_artists(
        self,
        releases: list[DiscogsRelease],
    ) -> None:
        self.relations_tree.clear()
        statistics = _label_artist_statistics(releases)
        if not statistics:
            self.relations_tree.addTopLevelItem(
                QTreeWidgetItem(
                    ["Keine Künstlerzuordnungen aus Releases ableitbar"]
                )
            )
            return
        parent = QTreeWidgetItem(
            [f"Auf Label-Veröffentlichungen vertreten ({len(statistics)})"]
        )
        parent.setToolTip(
            0,
            "Quelle: Discogs-Labelveröffentlichungen. Keine bestätigten Vertragsverhältnisse.",
        )
        font = parent.font(0)
        font.setBold(True)
        parent.setFont(0, font)
        self.relations_tree.addTopLevelItem(parent)
        for name, count, first_year, last_year in statistics:
            if not first_year and not last_year:
                period = "Zeitraum unbekannt"
            elif first_year == last_year:
                period = first_year
            else:
                period = f"{first_year or '?'}–{last_year or '?'}"
            count_text = (
                "1 Veröffentlichung"
                if count == 1
                else f"{count} Veröffentlichungen"
            )
            child = QTreeWidgetItem(
                [f"{name} · {count_text} · {period}"]
            )
            child.setData(
                0,
                Qt.ItemDataRole.UserRole,
                ("label_artist", name),
            )
            child.setToolTip(
                0,
                "Aus den Hauptkünstler-Angaben der Discogs-Releases abgeleitet.",
            )
            parent.addChild(child)
        self.relations_tree.expandAll()

    def _single_discogs_release_loaded(
        self,
        release,
    ) -> None:
        self._discogs_catalog_releases_loaded(
            [
                release
            ]
        )

    def _discogs_catalog_releases_loaded(
        self,
        result,
    ) -> None:
        if isinstance(result, DiscogsCatalogSnapshot):
            releases = list(result.releases)
            cache_note = (
                "lokale Discogs-Datenbank"
                if result.from_cache
                else "Discogs live"
            )
        else:
            releases = list(result)
            cache_note = "Discogs"
        self.discogs_releases = list(
            releases
        )
        self.discogs_release_groups = [
            self._group_from_discogs_release(
                release
            )
            for release in self.discogs_releases
        ]
        if self.current_catalog_kind == "label":
            self._render_discogs_label_artists(
                self.discogs_releases
            )
        self.release_groups = _merge_release_groups(
            self.musicbrainz_release_groups,
            self.discogs_release_groups,
        )
        self._render_release_groups()
        self._render_alternative_views()
        self._set_status(
            f"{len(self.release_groups)} zusammengeführte Veröffentlichungen "
            f"geladen ({cache_note})."
        )
        self.discogs_refresh_button.setEnabled(True)

    def _refresh_discogs_live(self) -> None:
        settings = load_settings()
        if not self.current_artist_name or not settings.discogs_token.strip():
            return
        self.discogs_refresh_button.setEnabled(False)
        self._set_status("Discogs wird live aktualisiert …")
        self._run(
            _fetch_discogs_catalog,
            self.current_artist_name,
            settings.discogs_token,
            force_refresh=True,
            finished=self._discogs_catalog_releases_loaded,
        )

    @staticmethod
    def _discogs_edition_from_group(
        group: ReleaseGroup,
    ) -> list[Edition]:
        return [
            Edition(
                release_id=group.release_group_id,
                title=group.title,
                date=group.first_release_date,
                label=", ".join(group.labels),
                format=", ".join(group.formats),
                source="discogs",
                category=group.category,
                labels=group.labels,
                formats=group.formats,
                badges=group.badges,
                external_url=group.external_url,
                cover_url=group.cover_url,
                discogs_release_id=group.discogs_release_id,
            )
        ]

    def _group_from_discogs_release(
        self,
        release: DiscogsRelease,
    ) -> ReleaseGroup:
        return ReleaseGroup(
            release_group_id=(
                release.source_id
            ),
            title=release.title,
            first_release_date=(
                release.year
            ),
            primary_type=(
                release.release_type
            ),
            artist=", ".join(
                release.artists
            ),
            source="discogs",
            category=release.category,
            labels=release.labels,
            formats=release.formats,
            badges=release.badges,
            external_url=(
                release.external_url
            ),
            cover_url=release.cover_url,
            discogs_release_id=(
                release.release_id
            ),
        )

    def _view_mode_changed(self, index: int) -> None:
        mode = str(self.view_mode_combo.itemData(index) or "discography")
        self.release_view_mode = mode
        self.release_view_stack.setCurrentIndex({"discography":0,"table":1,"covers":2,"cover_list":3}.get(mode,0))
        self.cover_size_combo.setEnabled(mode in {"covers","cover_list"})
        self.ui_settings.setValue("media_library/view_mode", mode)

    def _cover_size_changed(self, index: int) -> None:
        self.cover_size_name = str(self.cover_size_combo.itemData(index) or "medium")
        self.ui_settings.setValue("media_library/cover_size", self.cover_size_name)
        self._apply_cover_size(); self._render_alternative_views()

    def _cover_dimensions(self) -> tuple[int,int]:
        return {"small":(88,120),"medium":(128,168),"large":(176,222),"xlarge":(230,284)}.get(self.cover_size_name,(128,168))

    def _apply_cover_size(self) -> None:
        cover, cell = self._cover_dimensions()
        self.cover_view.setIconSize(QSize(cover,cover)); self.cover_view.setGridSize(QSize(cell,cell+54))
        list_cover = {
            "small": 44,
            "medium": 60,
            "large": 76,
            "xlarge": 96,
        }.get(self.cover_size_name, 60)
        self.cover_list.setIconSize(QSize(list_cover, list_cover))

    def _render_alternative_views(self) -> None:
        if not hasattr(self, "release_table"):
            return
        self._view_syncing = True; self.release_table.setSortingEnabled(False)
        self.release_table.setRowCount(len(self.release_groups)); self.cover_model.clear(); self.cover_list.clear()
        cover_size,_ = self._cover_dimensions(); placeholder=QPixmap(cover_size,cover_size); placeholder.fill(Qt.GlobalColor.transparent)
        for row, group in enumerate(self.release_groups):
            source = "Discogs" if group.source == "discogs" else "MusicBrainz"
            display_artist = (
                _streaming_artist(group.artist, self.current_artist_name)
                or "Unbekannter Künstler"
            )
            local = _local_status_display(
                self.local_album_status.get(
                    _normalized(group.title),
                    "Nicht vorhanden",
                )
            )
            extra = " · ".join([*group.labels[:2],*group.formats[:3]])
            values=(group.title,display_artist,group.first_release_date[:4],_category(group),source,extra,local)
            for col,value in enumerate(values):
                item=QTableWidgetItem(str(value or "")); item.setData(Qt.ItemDataRole.UserRole,row); self.release_table.setItem(row,col,item)
            grid=QStandardItem(QIcon(placeholder), f"{group.title}\n{display_artist}\n{group.first_release_date[:4]} · {local}")
            grid.setData(row,Qt.ItemDataRole.UserRole); grid.setEditable(False); self.cover_model.appendRow(grid)
            li=QListWidgetItem(QIcon(placeholder), f"{group.title}\n{display_artist} · {group.first_release_date[:4] or 'Jahr unbekannt'} · {_category(group)}\n{extra or source} · {local}")
            list_cover = self.cover_list.iconSize().height()
            li.setData(Qt.ItemDataRole.UserRole,row); li.setSizeHint(QSize(300,max(64,list_cover+10))); self.cover_list.addItem(li)
            self._load_release_thumbnail(row,group)
        self.release_table.setSortingEnabled(True); self.release_table.resizeColumnsToContents(); self._view_syncing=False

    def _load_release_thumbnail(self, row: int, group: ReleaseGroup) -> None:
        local_file=self.local_album_files.get(_normalized(group.title),"")
        if local_file:
            try:
                data=load_cover(local_file)
            except Exception:
                logger.debug("Thumbnail-Cover nicht ladbar: %s", local_file, exc_info=True)
                data=None
            if data:
                self._apply_release_thumbnail(
                    row, data, group.release_group_id
                ); return
        if group.cover_url:
            cache=self.cover_cache_directory / f"view-{group.source}-{group.release_group_id}.jpg"
            self._run_thumbnail(
                _fetch_url_cover,
                group.cover_url,
                cache,
                finished=lambda data,target=row,group_id=group.release_group_id:self._apply_release_thumbnail(target,data,group_id),
            )
        elif group.source == "musicbrainz":
            self._run_thumbnail(
                _fetch_release_group_cover_with_discogs,
                group.release_group_id,
                self.cover_cache_directory,
                self.current_artist_name or group.artist,
                group.title,
                group.first_release_date[:4],
                load_settings().discogs_token,
                finished=lambda data,target=row,group_id=group.release_group_id:self._apply_release_thumbnail(target,data,group_id),
            )

    def _apply_release_thumbnail(
        self,
        row: int,
        data: bytes | None,
        release_group_id: str = "",
    ) -> None:
        if not data or not (0 <= row < len(self.release_groups)): return
        if (
            release_group_id
            and self.release_groups[row].release_group_id != release_group_id
        ):
            return
        pix=QPixmap()
        if not pix.loadFromData(data): return
        size,_=self._cover_dimensions(); icon=QIcon(pix.scaled(size,size,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        item=self.cover_model.item(row)
        if item is not None: item.setIcon(icon)
        li=self.cover_list.item(row)
        if li is not None: li.setIcon(icon)

    def _sync_current_group_thumbnail(self, data: bytes) -> None:
        if self.current_group is None:
            return
        group_id = self.current_group.release_group_id
        for row, group in enumerate(self.release_groups):
            if group.release_group_id == group_id:
                self._apply_release_thumbnail(row, data, group_id)
                return

    def _select_release_index(self, index: int) -> None:
        if self._view_syncing or not (0 <= index < len(self.release_groups)): return
        self._load_group(self.release_groups[index])

    def _table_release_selected(self, row: int, column: int, previous_row: int, previous_column: int) -> None:
        if row < 0: return
        item=self.release_table.item(row,0)
        if item is not None: self._select_release_index(int(item.data(Qt.ItemDataRole.UserRole)))

    def _cover_release_selected(self, index) -> None:
        value=index.data(Qt.ItemDataRole.UserRole)
        if value is not None: self._select_release_index(int(value))

    def _cover_list_release_selected(self, row: int) -> None:
        item=self.cover_list.item(row)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) is not None: self._select_release_index(int(item.data(Qt.ItemDataRole.UserRole)))

    def _sort_discography_column(self, column: int) -> None:
        if column == self._discography_sort_column:
            self._discography_sort_ascending = not self._discography_sort_ascending
        else:
            self._discography_sort_column = column
            self._discography_sort_ascending = True

        reverse = not self._discography_sort_ascending
        for parent_index in range(self.group_tree.topLevelItemCount()):
            parent = self.group_tree.topLevelItem(parent_index)
            children = parent.takeChildren()
            children.sort(
                key=lambda item: item.text(column).casefold(),
                reverse=reverse,
            )
            parent.addChildren(children)

        self.group_tree.header().setSortIndicator(
            column,
            (
                Qt.SortOrder.AscendingOrder
                if self._discography_sort_ascending
                else Qt.SortOrder.DescendingOrder
            ),
        )

    def _load_group(self, group: ReleaseGroup) -> None:
        self.track_panel.show()
        self.current_group=group; self.current_tracks=[]; self.editions=[]; self.edition_combo.clear(); self.track_table.setRowCount(0)
        self.preview_player.stop(); self._preview_token += 1; self._playing_preview_row = -1; self.track_preview_buttons = []; self.track_preview_urls = []; self._row_is_local = []
        self._cover_generation += 1; self._show_cover(None); self.group_title.setText(group.title)
        self.prerelease_chip.hide(); self.prerelease_chip.clear()
        key=_normalized(group.title); local_path=self.local_albums.get(key); status=self.local_album_status.get(key,"Nicht vorhanden"); local_online=status == "Lokal verfügbar"
        self._push_breadcrumb(
            "release",
            group.title,
            group.release_group_id,
        )
        self.group_meta.setText(" · ".join(v for v in (_type_text(group),group.first_release_date or "Datum unbekannt") if v))
        chip_text, chip_style = _status_chip(status)
        self.local_status_chip.setText(chip_text)
        self.local_status_chip.setStyleSheet(chip_style)
        self._render_source_details(group, status)
        self.open_local_button.setProperty(
            "local_path",
            local_path or "",
        )
        self.open_local_button.setEnabled(bool(local_path) and local_online)
        self.enqueue_local_button.setEnabled(
            bool(local_path) and local_online
        )
        self.open_local_button.setToolTip(
            "Lokales Album im Tagger öffnen"
            if local_online
            else "Das Album ist indiziert, die Musikquelle ist momentan nicht erreichbar."
        )
        self.streaming_button.setEnabled(True)
        self.quality_button.setEnabled(True)
        self.apple_button.setEnabled(False)
        self.tidal_button.setEnabled(False)
        self.spotify_button.setEnabled(False)
        cached_streaming = self._streaming_results.get(group.release_group_id)
        if group.release_group_id not in self._streaming_results:
            cached_streaming = self._load_saved_streaming_result(group)
            if cached_streaming is not None:
                self._streaming_results[group.release_group_id] = cached_streaming
        if cached_streaming is not None:
            self._show_streaming_result(group, cached_streaming, saved=True)
        elif group.release_group_id in self._streaming_results:
            self._show_no_streaming_result(group)
        else:
            self.streaming_status.setText("Streaming und Qualität wurden nicht abgefragt.")
        apple_url = (
            "https://music.apple.com/de/album/"
            f"id{cached_streaming.collection_id}"
            if cached_streaming is not None
            else ""
        )
        self._request_editorial(
            f"album:{group.release_group_id}",
            "album",
            fetch_album_info_with_apple_fallback,
            self.current_artist_name or group.artist,
            group.title,
            self.language,
            apple_url,
        )
        if group.source == "discogs" and group.discogs_release_id:
            self._run(
                self._discogs_edition_from_group,
                group,
                finished=self._editions_loaded,
                transform=lambda editions,group_id=group.release_group_id:(group_id,editions),
            )
        else:
            self._run(
                fetch_release_group_editions,
                group.release_group_id,
                finished=self._editions_loaded,
                transform=lambda editions,group_id=group.release_group_id:(group_id,editions),
            )

    def _groups_loaded(
        self,
        result,
    ) -> None:
        if (
            isinstance(result, ReleaseGroupResponse)
            and result.artist_id != self.current_artist_id
        ):
            return
        if isinstance(
            result,
            ReleaseGroupResponse,
        ):
            self.musicbrainz_release_groups = list(
                result.release_groups
            )
            for trace in result.traces:
                self.search_debug_lines.append(
                    trace.as_text()
                )
        else:
            self.musicbrainz_release_groups = list(
                result
            )

        self.release_groups = _merge_release_groups(
            self.musicbrainz_release_groups,
            self.discogs_release_groups,
        )

        self._refresh_debug_output()
        self._render_release_groups()
        self._render_alternative_views()
        self._set_status(
            (
                f"{len(self.release_groups)} "
                "Veröffentlichungen geladen."
            )
        )

    def _render_release_groups(
        self,
    ) -> None:
        self.group_tree.clear()
        grouped: dict[
            str,
            list[
                tuple[
                    int,
                    ReleaseGroup,
                ]
            ],
        ] = {}

        for index, group in enumerate(
            self.release_groups
        ):
            grouped.setdefault(
                _category(
                    group
                ),
                [],
            ).append(
                (
                    index,
                    group,
                )
            )

        category_order = (
            "Alben",
            "Live",
            "EPs",
            "Singles",
            "Mixtapes",
            "Sampler",
            "Compilations",
            "Soundtracks",
            "Boxsets",
            "Bootlegs",
            "Sonstiges",
        )

        for category in category_order:
            entries = grouped.get(
                category,
                [],
            )

            if not entries:
                continue

            parent = QTreeWidgetItem(
                [
                    f"{category} ({len(entries)})",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            parent.setIcon(
                0,
                self._category_icons.get(
                    category,
                    self._category_icons[
                        "Sonstiges"
                    ],
                ),
            )
            parent.setFirstColumnSpanned(
                True
            )
            font = parent.font(
                0
            )
            font.setBold(
                True
            )
            parent.setFont(
                0,
                font,
            )
            self.group_tree.addTopLevelItem(
                parent
            )

            for index, group in entries:
                local_key = _normalized(
                    group.title
                )
                source_text = (
                    "Discogs"
                    if group.source
                    == "discogs"
                    else "MusicBrainz"
                )
                raw_status = self.local_album_status.get(
                    local_key,
                    "Nicht vorhanden",
                )
                item = QTreeWidgetItem(
                    [
                        group.title,
                        group.first_release_date[
                            :4
                        ],
                        _category(
                            group
                        ),
                        source_text,
                        raw_status,
                    ]
                )
                # Ampel als farbiger Punkt (statt Emoji) in der Status-Spalte.
                item.setIcon(4, _status_dot_icon(raw_status))
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    index,
                )
                tooltip_parts = [
                    *group.labels,
                    *group.formats,
                    *group.badges,
                ]

                if tooltip_parts:
                    item.setToolTip(
                        0,
                        " · ".join(
                            dict.fromkeys(
                                tooltip_parts
                            )
                        ),
                    )

                parent.addChild(
                    item
                )

        self.group_tree.expandAll()
        self.group_tree.resizeColumnToContents(
            1
        )
        self.group_tree.resizeColumnToContents(
            2
        )
        self.group_tree.resizeColumnToContents(
            3
        )
        self.group_tree.header().setSortIndicator(
            self._discography_sort_column,
            (
                Qt.SortOrder.AscendingOrder
                if self._discography_sort_ascending
                else Qt.SortOrder.DescendingOrder
            ),
        )
        categories = sum(
            1
            for category in category_order
            if grouped.get(
                category
            )
        )
        self._set_status(
            f"{len(self.release_groups)} Veröffentlichungen "
            f"in {categories} Kategorien geladen."
        )

    def _group_selected(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        if current is None: return
        index=current.data(0,Qt.ItemDataRole.UserRole)
        if index is not None: self._select_release_index(int(index))

    def _editions_loaded(
        self,
        editions,
    ) -> None:
        if (
            isinstance(editions, tuple)
            and len(editions) == 2
            and isinstance(editions[0], str)
        ):
            release_group_id, editions = editions
            if (
                self.current_group is None
                or self.current_group.release_group_id != release_group_id
            ):
                return
        self.editions = list(
            editions
        )
        self.edition_combo.blockSignals(
            True
        )
        self.edition_combo.clear()

        for edition in self.editions:
            details = [
                edition.date
                or "ohne Datum",
                edition.country
                or "ohne Land",
                (
                    f"{edition.medium_count} CD(s)"
                ),
                (
                    f"{edition.track_count} Titel"
                ),
            ]

            if edition.format:
                details.append(
                    edition.format
                )

            self.edition_combo.addItem(
                f"{edition.title} · "
                + " · ".join(
                    details
                )
            )

        self.edition_combo.blockSignals(
            False
        )

        if self.editions:
            self.edition_combo.setCurrentIndex(
                0
            )
            self._edition_selected(
                0
            )
        else:
            self.edition_details.setText(
                "Keine konkreten Editionen gefunden."
            )

    def _edition_selected(
        self,
        index: int,
    ) -> None:
        if (
            index < 0
            or index >= len(
                self.editions
            )
        ):
            return

        edition = self.editions[
            index
        ]
        self.edition_details.setText(
            " · ".join(
                value
                for value in (
                    (
                        f"{edition.medium_count} CD(s)"
                    ),
                    (
                        f"{edition.track_count} Titel"
                    ),
                    edition.date,
                    edition.country,
                    edition.status,
                    edition.format,
                    edition.label,
                )
                if value
            )
        )
        self.track_table.setRowCount(
            0
        )
        self._load_edition_cover(
            edition
        )
        self._set_status(
            "Trackliste wird geladen …"
        )
        if (
            edition.source == "discogs"
            and edition.discogs_release_id
        ):
            settings = load_settings()
            self._run(
                fetch_discogs_release_tracks,
                edition.discogs_release_id,
                settings.discogs_token,
                finished=self._discogs_tracks_loaded,
            )
        else:
            self._run(
                fetch_release_tracklist,
                edition.release_id,
                finished=self._tracks_loaded,
            )

    def _tracks_loaded(
        self,
        tracks,
    ) -> None:
        tracks = list(
            tracks
        )
        self.current_tracks = tracks
        self.preview_player.stop()
        self._playing_preview_row = -1
        self.track_preview_buttons = []
        self.track_preview_urls = [""] * len(tracks)

        # Lokale Verfügbarkeit pro Zeile bestimmen (für vollen Song statt
        # Vorschau). Ist nichts lokal, bleiben alle Werte None/False.
        local_songs = self._current_local_album_songs()
        matched_local: list[Song | None] = []
        for track in tracks:
            song = None
            if local_songs:
                index = self._match_local_index(track, local_songs)
                if index >= 0:
                    song = local_songs[index]
            matched_local.append(song)
        self._row_is_local = [song is not None for song in matched_local]
        self.track_table.setRowCount(
            len(tracks)
        )

        for row, track in enumerate(
            tracks
        ):
            title_text = _track_title(track)
            duration_text = _duration(track.length_ms)
            # Liefert der Anbieter einen Platzhalter („Track 11") und liegt die
            # Datei lokal vor, den echten lokalen Titel + Dauer anzeigen.
            local_song = matched_local[row]
            if local_song is not None and _is_placeholder_title(track.title):
                title_text = (
                    f"{local_song.title} - {local_song.artist}"
                    if local_song.artist
                    else local_song.title
                )
                if not duration_text:
                    duration_text = _duration(local_duration_ms(local_song.path))
            values = (
                str(
                    track.disc_number
                ),
                f"{track.track_number:02d}",
                title_text,
                duration_text,
            )

            for column, value in enumerate(
                values
            ):
                self.track_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(
                        value
                    ),
                )

            preview_button = QPushButton()
            self._set_preview_button_icon(preview_button, "play")
            preview_button.setEnabled(False)
            preview_button.clicked.connect(
                lambda _checked=False, index=row: self._play_track(index)
            )
            self.track_preview_buttons.append(preview_button)
            self.track_table.setCellWidget(
                row,
                4,
                preview_button,
            )

        self.track_table.resizeColumnsToContents()
        self._set_status(
            f"{len(tracks)} Titel geladen."
        )
        self._refresh_track_preview_buttons()
        self._start_preview_resolution(tracks)

    def _discogs_tracks_loaded(
        self,
        result,
    ) -> None:
        discogs_tracks, _payload = result
        tracks = []
        for fallback, track in enumerate(discogs_tracks, start=1):
            disc_number, track_number = _discogs_position(
                track.position,
                fallback,
            )
            tracks.append(
                Track(
                    disc_number=disc_number,
                    track_number=track_number,
                    title=track.title,
                    artist=track.artist,
                    length_ms=_duration_ms(track.duration),
                )
            )
        self._tracks_loaded(tracks)

    def _start_preview_resolution(self, tracks: list) -> None:
        group = self.current_group

        if group is None or not tracks:
            return

        # Liegt das gesamte Album lokal vor, wird keine Vorschau benötigt.
        if self._row_is_local and all(self._row_is_local):
            return

        # Token schützt vor veralteten Ergebnissen, wenn schnell ein anderes
        # Album gewählt wird.
        self._preview_token += 1
        token = self._preview_token

        settings = load_settings()

        if settings.preview_source == "apple_music":
            self._run(
                _resolve_apple_previews,
                group.title,
                group.artist,
                len(tracks),
                settings.apple_country,
                finished=lambda mapping, resolved_token=token: (
                    self._previews_resolved(resolved_token, mapping)
                ),
                failed=lambda _error: None,
            )
        else:
            self._run(
                _resolve_deezer_previews,
                group.title,
                group.artist,
                len(tracks),
                finished=lambda mapping, resolved_token=token: (
                    self._previews_resolved(resolved_token, mapping)
                ),
                failed=lambda _error: None,
            )

    def _previews_resolved(
        self,
        token: int,
        mapping: dict,
    ) -> None:
        if token != self._preview_token:
            return

        for row, track in enumerate(self.current_tracks):
            if row >= len(self.track_preview_urls):
                break

            # Reiner Titel ohne Künstler-Suffix (track_title hängt " - Artist"
            # an; die Streaming-Map ist aber nur nach dem Titel verschlüsselt).
            key = _preview_title_key(getattr(track, "title", ""))
            self.track_preview_urls[row] = mapping.get(key, "")

        self._refresh_track_preview_buttons()

    def _play_track(self, row: int) -> None:
        """Ein-Klick-Wiedergabe: voller lokaler Titel, sonst 30-Sek-Vorschau."""
        songs, start_index = self._local_playback_for_row(row)

        if songs and start_index >= 0:
            # Lokal vorhanden -> vollen Titel über die normale Leiste spielen.
            self.preview_player.stop()
            self._playing_preview_row = -1
            self._refresh_track_preview_buttons()
            self.play_local_tracks.emit(songs, start_index)
            return

        self._toggle_track_preview(row)

    def _toggle_track_preview(self, row: int) -> None:
        if not (0 <= row < len(self.track_preview_urls)):
            return

        url = self.track_preview_urls[row]

        if not url:
            return

        # Läuft genau diese Zeile bereits, wird gestoppt – andernfalls startet
        # die neue Vorschau. Der Zeilenindex wird synchron gemerkt, damit die
        # Hervorhebung unabhängig von URL-Kollisionen korrekt bleibt.
        if row == self._playing_preview_row and self.preview_player.is_playing():
            self._playing_preview_row = -1
            self.preview_player.stop()
            return

        self._playing_preview_row = row
        title = (
            _track_title(self.current_tracks[row])
            if 0 <= row < len(self.current_tracks)
            else ""
        )
        self.preview_player.play(url, title)

        if title:
            self._set_status(f"Vorschau wird geladen: {title} …")

    def _on_preview_error(self, message: str) -> None:
        self._playing_preview_row = -1
        self._refresh_track_preview_buttons()
        self._set_status(message)

    def _refresh_track_preview_buttons(self) -> None:
        playing = self.preview_player.is_playing()

        for row, button in enumerate(self.track_preview_buttons):
            # Lokale Tracks: der Knopf spielt den vollen Titel (über die
            # normale Wiedergabe-Leiste), keine Vorschau-Markierung.
            if row < len(self._row_is_local) and self._row_is_local[row]:
                button.setEnabled(True)
                self._set_preview_button_icon(button, "play")
                button.setToolTip(
                    "Vollen Titel abspielen (lokal vorhanden)"
                )
                continue

            url = (
                self.track_preview_urls[row]
                if row < len(self.track_preview_urls)
                else ""
            )
            button.setEnabled(bool(url))
            is_active = playing and row == self._playing_preview_row
            self._set_preview_button_icon(button, "pause" if is_active else "play")
            button.setToolTip("30-Sekunden-Vorschau abspielen")

    def _set_preview_button_icon(self, button: QPushButton, name: str) -> None:
        """Setzt das SVG-Play/Pause-Icon eines Vorschau-Knopfs (Palette-Farbe).

        Die Eigenschaft ``previewState`` spiegelt den Zustand ("play"/"pause")
        unabhängig vom gerenderten Icon wider.
        """
        color = self.palette().color(QPalette.ColorRole.ButtonText).name()
        button.setIcon(make_icon(name, color))
        button.setIconSize(QSize(16, 16))
        button.setProperty("previewState", name)

    def _on_preview_state(self, _url: str, playing: bool) -> None:
        self._refresh_track_preview_buttons()

        # Der Vorschau-Player ist bewusst getrennt von der unteren
        # Wiedergabe-Leiste (die spielt lokale Dateien). Damit klar ist, dass
        # gerade eine Vorschau läuft, wird der Status entsprechend gesetzt.
        if (
            playing
            and 0 <= self._playing_preview_row < len(self.current_tracks)
        ):
            title = _track_title(
                self.current_tracks[self._playing_preview_row]
            )
            self._set_status(f"Vorschau läuft: {title}")
        elif not playing and self.current_tracks:
            self._set_status(
                f"{len(self.current_tracks)} Titel geladen."
            )

    def _load_category_icons(
        self,
    ) -> dict[
        str,
        QIcon,
    ]:
        icon_directory = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "icons"
        )

        return {
            "Alben": QIcon(
                str(
                    icon_directory
                    / "album.svg"
                )
            ),
            "Live": QIcon(
                str(
                    icon_directory
                    / "live.svg"
                )
            ),
            "EPs": QIcon(
                str(
                    icon_directory
                    / "ep.svg"
                )
            ),
            "Singles": QIcon(
                str(
                    icon_directory
                    / "single.svg"
                )
            ),
            "Mixtapes": QIcon(
                str(
                    icon_directory
                    / "mixtape.svg"
                )
            ),
            "Sampler": QIcon(
                str(
                    icon_directory
                    / "sampler.svg"
                )
            ),
            "Compilations": QIcon(
                str(
                    icon_directory
                    / "compilation.svg"
                )
            ),
            "Soundtracks": QIcon(
                str(
                    icon_directory
                    / "soundtrack.svg"
                )
            ),
            "Boxsets": QIcon(
                str(
                    icon_directory
                    / "boxset.svg"
                )
            ),
            "Bootlegs": QIcon(
                str(
                    icon_directory
                    / "bootleg.svg"
                )
            ),
            "Broadcasts": QIcon(
                str(
                    icon_directory
                    / "other.svg"
                )
            ),
            "Sonstiges": QIcon(
                str(
                    icon_directory
                    / "other.svg"
                )
            ),
        }

    def _load_edition_cover(
        self,
        edition: Edition,
    ) -> None:
        self._cover_generation += 1
        generation = (
            self._cover_generation
        )
        self.cover_label.setText(
            "Cover wird geladen …"
        )
        self.cover_label.setPixmap(
            QPixmap()
        )

        group = self.current_group
        local_file = ""

        if group is not None:
            local_file = self.local_album_files.get(
                _normalized(
                    group.title
                ),
                "",
            )

        if local_file:
            try:
                data = load_cover(
                    local_file
                )
            except Exception:
                logger.debug(
                    "Detail-Cover nicht ladbar: %s", local_file, exc_info=True
                )
                data = None

            if data:
                self._cover_loaded(
                    (
                        generation,
                        edition.release_id,
                        data,
                    )
                )
                return

        if edition.cover_url:
            self._run(
                _fetch_url_cover,
                edition.cover_url,
                self.cover_cache_directory
                / f"discogs-{edition.discogs_release_id}.jpg",
                finished=self._cover_loaded,
                transform=lambda data: (
                    generation,
                    edition.release_id,
                    data,
                ),
            )
            return

        self._run(
            _fetch_release_cover_with_discogs,
            edition.release_id,
            self.cover_cache_directory,
            self.current_artist_name,
            edition.title,
            edition.date[:4],
            load_settings().discogs_token,
            finished=self._cover_loaded,
            transform=lambda data: (
                generation,
                edition.release_id,
                data,
            ),
        )

    def _cover_loaded(
        self,
        result,
    ) -> None:
        (
            generation,
            release_id,
            data,
        ) = result

        if (
            generation
            != self._cover_generation
        ):
            return

        index = self.edition_combo.currentIndex()

        if (
            index < 0
            or index >= len(
                self.editions
            )
            or self.editions[
                index
            ].release_id
            != release_id
        ):
            return

        self._show_cover(
            data
        )

    def _show_cover(
        self,
        data: bytes | None,
    ) -> None:
        self._current_cover_data = data

        if not data:
            self.cover_label.setPixmap(
                QPixmap()
            )
            self.cover_label.setText(
                "Kein Cover verfügbar"
            )
            return

        pixmap = QPixmap()
        loaded = pixmap.loadFromData(
            data
        )

        if not loaded:
            self.cover_label.setText(
                "Cover nicht lesbar"
            )
            return

        self.cover_label.setText("")
        self.cover_label.setPixmap(
            pixmap.scaled(
                self.cover_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._sync_current_group_thumbnail(data)

    def _artist_artwork_loaded(self, result) -> None:
        artist_id, artwork = result
        if artist_id != self.current_artist_id or self.current_group is not None:
            return
        if not isinstance(artwork, ArtistArtwork):
            self._artist_artwork_failed(artist_id)
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(artwork.data):
            self._artist_artwork_failed(artist_id)
            return
        size = self.cover_label.size()
        scaled = pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - size.width()) // 2)
        y = max(0, (scaled.height() - size.height()) // 2)
        self.cover_label.setText("")
        self.cover_label.setPixmap(scaled.copy(x, y, size.width(), size.height()))
        self.cover_label.setToolTip(
            f"Künstlerbild von {artwork.source}\n{artwork.artist_url}"
        )

    def _artist_artwork_failed(self, artist_id: str) -> None:
        if artist_id != self.current_artist_id or self.current_group is not None:
            return
        self.cover_label.setPixmap(QPixmap())
        self.cover_label.setText("Kein Künstlerbild verfügbar")
        self.cover_label.setToolTip(
            "Weder Apple Music noch Discogs stellen ein geeignetes "
            "Künstlerbild bereit."
        )

    def check_streaming(
        self,
    ) -> None:
        group = self.current_group

        if group is None:
            return

        self.streaming_button.setEnabled(
            False
        )
        self.streaming_status.setText(
            "Apple Music, TIDAL und Spotify werden geprüft …"
        )
        expected_track_count = None
        edition_index = self.edition_combo.currentIndex()
        if 0 <= edition_index < len(self.editions):
            expected_track_count = self.editions[edition_index].track_count or None
        settings = load_settings()
        self._run(
            check_streaming_providers,
            group.title,
            _streaming_artist(group.artist, self.current_artist_name),
            expected_track_count=expected_track_count,
            track_titles=tuple(track.title for track in self.current_tracks),
            wanted_year=(
                group.first_release_date[
                    :4
                ]
            ),
            country="DE",
            tidal_client_id=settings.tidal_client_id,
            tidal_client_secret=get_secret(TIDAL_CLIENT_SECRET),
            spotify_client_id=settings.spotify_client_id,
            spotify_client_secret=get_secret(SPOTIFY_CLIENT_SECRET),
            finished=self._streaming_loaded,
            transform=lambda report, group_id=group.release_group_id: (
                group_id,
                report,
            ),
        )

    def _streaming_loaded(
        self,
        result,
    ) -> None:
        group_id, report = result
        if (
            self.current_group is None
            or self.current_group.release_group_id != group_id
        ):
            return
        if not isinstance(report, StreamingCheckReport):
            return
        self.streaming_button.setEnabled(
            True
        )
        self._provider_streaming_results[group_id] = dict(report.results)
        self._provider_streaming_errors[group_id] = dict(report.errors)
        for availability in report.results.values():
            self.streaming_cache.put(availability)
        self._apply_provider_buttons(report.results)

        apple_result = report.results.get("apple_music")
        if (
            apple_result is None
            or apple_result.status is not AvailabilityStatus.AVAILABLE
        ):
            self._streaming_results[group_id] = None
            self._show_no_streaming_result(self.current_group)
            return

        best = AppleAlbumCandidate(
            collection_id=apple_result.external_id,
            album=apple_result.album,
            artist=apple_result.artist,
            track_count=apple_result.track_count,
            year=apple_result.year,
            country=apple_result.country,
            confidence=apple_result.confidence,
            release_date=apple_result.release_date,
        )
        self._streaming_results[group_id] = best
        self._streaming_checked_at[group_id] = datetime.fromisoformat(
            apple_result.checked_at
        )
        self._show_streaming_result(self.current_group, best)
        self._request_editorial(
            f"album:{self.current_group.release_group_id}",
            "album",
            fetch_album_info_with_apple_fallback,
            self.current_artist_name or self.current_group.artist,
            self.current_group.title,
            self.language,
            (
                "https://music.apple.com/de/album/"
                f"id{best.collection_id}"
            ),
        )

    def _show_streaming_result(
        self,
        group: ReleaseGroup,
        best: AppleAlbumCandidate,
        *,
        saved: bool = False,
    ) -> None:
        checked_at = self._streaming_checked_at.get(
            group.release_group_id,
            datetime.now().astimezone(),
        )
        checked_hint = (
            ("Gespeichertes Ergebnis · " if saved else "")
            + "Zuletzt geprüft: "
            + checked_at.astimezone().strftime("%d.%m.%Y, %H:%M")
            + ". "
        )
        url = (
            "https://music.apple.com/de/album/"
            f"id{best.collection_id}"
        )
        self.apple_button.setProperty(
            "url",
            url,
        )
        self.apple_button.setEnabled(
            True
        )
        self.streaming_status.setText(
            "Apple Music: gefunden · "
            f"{best.track_count} Titel · "
            f"Übereinstimmung {best.confidence} %. "
            + checked_hint
            + self._additional_streaming_summary(group.release_group_id)
        )
        status = self.local_album_status.get(_normalized(group.title), "Nicht vorhanden")
        self._render_source_details(group, status, apple_music_status="found")
        self._update_prerelease_chip(getattr(best, "release_date", ""))

    def _update_prerelease_chip(self, release_date: str) -> None:
        """Zeigt den Vorab-Chip nur bei tagesgenauem Zukunftsdatum."""
        if not is_prerelease_date(release_date):
            self.prerelease_chip.hide()
            self.prerelease_chip.clear()
            return
        self.prerelease_chip.setText(
            f"Vorabveröffentlichung · {localized_date(release_date)}"
        )
        self.prerelease_chip.setStyleSheet(
            "QLabel#prereleaseChip { color: #ffffff; background: #6f42c1;"
            " border-radius: 8px; padding: 2px 10px; font-size: 11px;"
            " font-weight: 600; }"
        )
        self.prerelease_chip.setToolTip(
            "Bei Apple als Vorabveröffentlichung gelistet; einige Titel sind "
            "möglicherweise noch nicht erschienen."
        )
        self.prerelease_chip.show()

    def _show_no_streaming_result(self, group: ReleaseGroup) -> None:
        self.apple_button.setEnabled(False)
        self.prerelease_chip.hide()
        self.streaming_status.setText(
            "Apple Music: keine eindeutige Ausgabe gefunden. "
            + self._streaming_checked_hint(group.release_group_id)
            + self._additional_streaming_summary(group.release_group_id)
        )
        status = self.local_album_status.get(_normalized(group.title), "Nicht vorhanden")
        self._render_source_details(group, status, apple_music_status="not_found")

    def _streaming_checked_hint(self, group_id: str) -> str:
        checked_values = [
            result.checked_at
            for result in self._provider_streaming_results.get(group_id, {}).values()
            if result.checked_at
        ]
        if not checked_values:
            return ""
        try:
            checked_at = max(datetime.fromisoformat(value) for value in checked_values)
        except ValueError:
            return ""
        return (
            "Zuletzt geprüft: "
            + checked_at.astimezone().strftime("%d.%m.%Y, %H:%M")
            + ". "
        )

    def _additional_streaming_summary(self, group_id: str) -> str:
        results = self._provider_streaming_results.get(group_id, {})
        errors = self._provider_streaming_errors.get(group_id, {})
        parts: list[str] = []
        for provider, label in (("tidal", "TIDAL"), ("spotify", "Spotify")):
            result = results.get(provider)
            if result is not None:
                if result.status is AvailabilityStatus.AVAILABLE:
                    parts.append(
                        f"{label}: gefunden ({result.confidence} %)"
                    )
                else:
                    parts.append(f"{label}: nicht gefunden")
            elif provider in errors:
                parts.append(f"{label}: Fehler ({errors[provider]})")
            else:
                parts.append(f"{label}: nicht eingerichtet")
        return " · ".join(parts) + "."

    def _apply_provider_buttons(
        self,
        results: dict[str, StreamingAvailability],
    ) -> None:
        for provider, button in (
            ("tidal", self.tidal_button),
            ("spotify", self.spotify_button),
        ):
            result = results.get(provider)
            url = (
                result.external_url
                if result is not None
                and result.status is AvailabilityStatus.AVAILABLE
                else ""
            )
            button.setProperty("url", url)
            button.setEnabled(bool(url))

    def _streaming_release_key(self, group: ReleaseGroup) -> str:
        return streaming_release_key(
            _streaming_artist(group.artist, self.current_artist_name),
            group.title,
            group.first_release_date[:4],
        )

    def _save_streaming_result(
        self, group: ReleaseGroup, result: AppleAlbumCandidate
    ) -> None:
        cached = StreamingAvailability.available(
            provider="apple_music",
            release_key=self._streaming_release_key(group),
            external_id=result.collection_id,
            external_url=(
                "https://music.apple.com/de/album/"
                f"id{result.collection_id}"
            ),
            album=result.album,
            artist=result.artist,
            year=result.year,
            track_count=result.track_count,
            confidence=result.confidence,
            country=result.country or "DE",
            ttl_days=7,
        )
        self.streaming_cache.put(cached)
        self._streaming_checked_at[group.release_group_id] = datetime.fromisoformat(
            cached.checked_at
        )

    def _load_saved_streaming_result(
        self, group: ReleaseGroup
    ) -> AppleAlbumCandidate | None:
        release_key = self._streaming_release_key(group)
        provider_results = {
            provider: cached
            for provider in ("apple_music", "tidal", "spotify")
            if (
                cached := self.streaming_cache.get(provider, release_key, "DE")
            )
            is not None
        }
        if provider_results:
            self._provider_streaming_results[group.release_group_id] = (
                provider_results
            )
            self._apply_provider_buttons(provider_results)
        cached = provider_results.get("apple_music")
        if cached is None or cached.status is not AvailabilityStatus.AVAILABLE:
            if provider_results:
                self._streaming_results[group.release_group_id] = None
            return None
        checked_at = datetime.fromisoformat(cached.checked_at)
        self._streaming_checked_at[group.release_group_id] = checked_at
        return AppleAlbumCandidate(
            collection_id=cached.external_id,
            album=cached.album or group.title,
            artist=cached.artist or group.artist,
            track_count=cached.track_count,
            year=cached.year,
            country=cached.country,
            confidence=cached.confidence,
            release_date=cached.release_date,
        )

    def _render_source_details(
        self,
        group: ReleaseGroup,
        local_status: str,
        *,
        apple_music_status: str = "not_checked",
    ) -> None:
        rows = _release_source_details(
            group,
            local_status,
            apple_music_status=apple_music_status,
        )
        compact_rows = []
        tooltip_rows = []
        for source, detail in rows:
            compact_detail = detail
            parts = [part.strip() for part in detail.split(",") if part.strip()]
            if source == "Discogs" and len(parts) > 2:
                compact_detail = (
                    f"{parts[0]}, {parts[1]} + {len(parts) - 2} weitere"
                )
            compact_rows.append((source, compact_detail))
            tooltip_rows.append(f"{source}: {detail}")
        content = "".join(
            f"<div><b>{html.escape(source)}</b> · {html.escape(detail)}</div>"
            for source, detail in compact_rows
        )
        self.source_details.setText(f"<b>Quellen</b>{content}")
        self.source_details.setToolTip("\n".join(tooltip_rows))
        self.source_details.show()

    def check_quality(
        self,
    ) -> None:
        QMessageBox.information(
            self,
            "Qualitätsprüfung",
            (
                "Die Qualitätsprüfung bleibt bewusst manuell. "
                "Für verlässliche Bit-Tiefen und Abtastraten werden "
                "noch die offiziellen beziehungsweise autorisierten "
                "Schnittstellen von Qobuz, TIDAL und Deezer benötigt. "
                "MusicTagStudio zeigt deshalb derzeit keine geratenen Werte an."
            ),
        )

    def open_apple(
        self,
    ) -> None:
        url = str(
            self.apple_button.property(
                "url"
            )
            or ""
        )

        if url:
            webbrowser.open(
                url
            )

    @staticmethod
    def _open_streaming_provider(button: QPushButton) -> None:
        url = str(button.property("url") or "")
        if url:
            webbrowser.open(url)

    def _open_local(
        self,
    ) -> None:
        path = str(
            self.open_local_button.property(
                "local_path"
            )
            or ""
        )

        if path:
            self.open_local_album.emit(
                path
            )

    def _refresh_local_markers(
        self,
    ) -> None:
        for top_index in range(
            self.group_tree.topLevelItemCount()
        ):
            parent = self.group_tree.topLevelItem(
                top_index
            )

            for child_index in range(
                parent.childCount()
            ):
                item = parent.child(
                    child_index
                )
                value = item.data(
                    0,
                    Qt.ItemDataRole.UserRole,
                )

                if value is None:
                    continue

                group = self.release_groups[
                    int(
                        value
                    )
                ]
                key = _normalized(
                    group.title
                )
                raw_status = self.local_album_status.get(
                    key,
                    "Nicht vorhanden",
                )
                item.setText(4, raw_status)
                item.setIcon(4, _status_dot_icon(raw_status))

        self._render_alternative_views()

    def _push_breadcrumb(
        self,
        kind: str,
        label: str,
        identifier: str,
    ) -> None:
        entry = (kind, str(label), str(identifier))
        if kind == "artist" and self.breadcrumbs:
            if self.breadcrumbs[-1][0] == "release":
                self.breadcrumbs.pop()
            if self.breadcrumbs and self.breadcrumbs[-1] == entry:
                self._render_breadcrumbs()
                return
        if kind == "release" and self.breadcrumbs:
            if self.breadcrumbs[-1][0] == "release":
                self.breadcrumbs[-1] = entry
            else:
                self.breadcrumbs.append(entry)
        elif not self.breadcrumbs or self.breadcrumbs[-1] != entry:
            self.breadcrumbs.append(entry)
        self._render_breadcrumbs()

    def _render_breadcrumbs(self) -> None:
        if not self.breadcrumbs:
            self.breadcrumb_label.clear()
            self.breadcrumb_label.hide()
            return
        links = [
            f'<a href="breadcrumb:{index}">{html.escape(label)}</a>'
            for index, (_kind, label, _identifier) in enumerate(
                self.breadcrumbs
            )
        ]
        self.breadcrumb_label.setText(
            " <span style='color:#888'>›</span> ".join(links)
        )
        self.breadcrumb_label.show()

    def _breadcrumb_activated(self, link: str) -> None:
        if not link.startswith("breadcrumb:"):
            return
        try:
            index = int(link.split(":", 1)[1])
            kind, label, identifier = self.breadcrumbs[index]
        except (ValueError, IndexError):
            return
        self.breadcrumbs = self.breadcrumbs[: index + 1]
        self._render_breadcrumbs()
        if kind == "artist":
            self.search_artist(label, preserve_breadcrumbs=True)
            return
        for group in self.release_groups:
            if group.release_group_id == identifier:
                self._load_group(group)
                return

    def _run(
        self,
        function,
        *args,
        finished,
        transform=None,
        failed=None,
        **kwargs,
    ) -> None:
        self._start_worker(
            self.thread_pool,
            function,
            *args,
            finished=finished,
            transform=transform,
            failed=failed,
            **kwargs,
        )

    def _run_thumbnail(
        self,
        function,
        *args,
        finished,
        transform=None,
        failed=None,
        **kwargs,
    ) -> None:
        self._start_worker(
            self.thumbnail_pool,
            function,
            *args,
            finished=finished,
            transform=transform,
            failed=failed,
            **kwargs,
        )

    def _start_worker(
        self,
        pool: QThreadPool,
        function,
        *args,
        finished,
        transform=None,
        failed=None,
        **kwargs,
    ) -> None:
        worker = Worker(
            function,
            *args,
            **kwargs,
        )
        self._workers.add(
            worker
        )

        def release(
            _value=None,
            current=worker,
        ):
            self._workers.discard(
                current
            )

        if transform is None:
            worker.signals.finished.connect(
                finished
            )
        else:
            worker.signals.finished.connect(
                lambda value:
                finished(
                    transform(
                        value
                    )
                )
            )
        worker.signals.finished.connect(
            release
        )
        worker.signals.failed.connect(failed or self._failed)
        worker.signals.failed.connect(
            release
        )
        pool.start(
            worker
        )

    def _failed(
        self,
        message: str,
    ) -> None:
        self.search_button.setEnabled(
            True
        )
        self.discogs_refresh_button.setEnabled(
            bool(load_settings().discogs_token.strip())
            and bool(self.current_artist_name)
        )
        self.streaming_button.setEnabled(
            self.current_group
            is not None
        )
        self.group_title.setText(
            "Suche fehlgeschlagen"
        )
        self.group_meta.setText(
            message
        )
        self.search_debug_lines.append(
            "Fehler: " + message
        )
        self._refresh_debug_output()
        self.suggestion_label.hide()
        self._set_status(
            "Fehler: "
            + message
        )

    def _request_editorial(
        self,
        key: str,
        kind: str,
        function,
        *args,
    ) -> None:
        language = information_language(self.language)
        request_key = f"{key}:{language}"
        self._editorial_request_key = request_key
        self._editorial_heading = ""
        self._editorial_text = ""
        self._editorial_source_html = ""
        self.editorial_more_button.hide()
        heading = (
            "Künstlerbiografie" if kind == "artist" else "Über dieses Album"
        ) if language == "de" else (
            "Artist biography" if kind == "artist" else "About this album"
        )
        loading = "Wird geladen …" if language == "de" else "Loading …"
        self.editorial_info.setHtml(
            f"<b>{html.escape(heading)}</b><p>{loading}</p>"
        )
        self.editorial_info.show()
        self._run(
            function,
            *args,
            finished=lambda info, current=request_key, title=heading:
                self._editorial_loaded(current, title, info),
            failed=lambda _message, current=request_key:
                self._editorial_failed(current),
        )

    def _editorial_loaded(
        self,
        request_key: str,
        heading: str,
        info: EditorialInfo | None,
    ) -> None:
        if request_key != self._editorial_request_key:
            return
        if info is None:
            self.editorial_info.hide()
            self.editorial_more_button.hide()
            return
        requested = information_language(self.language)
        if requested == "de":
            language_note = (
                "Deutsch" if info.language == "de" else "Englisch (Fallback)"
            )
            source_label = "Quelle"
        else:
            language_note = "English"
            source_label = "Source"
        body = html.escape(info.text).replace("\n", "<br>")
        source_html = (
            f'{source_label}: <a href="{html.escape(info.source_url)}">'
            f"{html.escape(info.source)}</a> · {language_note}"
        )
        self._editorial_heading = heading
        self._editorial_text = info.text
        self._editorial_source_html = source_html
        self.editorial_info.setHtml(
            f"<b>{html.escape(heading)}</b>"
            f"<p>{body}</p>"
            f"<small>{source_html}</small>"
        )
        self.editorial_info.show()
        self.editorial_more_button.setText(
            "Mehr anzeigen …" if requested == "de" else "Show more …"
        )
        self.editorial_more_button.setVisible(len(info.text) > 180)

    def _editorial_failed(self, request_key: str) -> None:
        if request_key == self._editorial_request_key:
            self.editorial_info.hide()
            self.editorial_more_button.hide()

    def _show_full_editorial(self) -> None:
        if not self._editorial_text:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self._editorial_heading)
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        body = html.escape(self._editorial_text).replace("\n", "<br>")
        browser.setHtml(
            f"<h2>{html.escape(self._editorial_heading)}</h2>"
            f"<p>{body}</p><hr><small>{self._editorial_source_html}</small>"
        )
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _set_status(
        self,
        text: str,
    ) -> None:
        self.streaming_status.setText(
            text
        )


# Compatibility adapters for callers and tests that historically patched the
# widget module's provider functions. New code belongs in media_library.tasks.


def _tag_number(value: str) -> int:
    """Return the leading tag number from values such as ``02/14``."""
    text = str(value or "").strip()
    match = re.match(r"\d+", text)
    return int(match.group()) if match else 0


def _search_exact_discogs_catalog(query: str, token: str):
    _catalog_tasks.search_catalog = search_catalog
    return _catalog_tasks._search_exact_discogs_catalog(query, token)


def _fetch_discogs_catalog(
    entity_name: str,
    token: str,
    *,
    force_refresh: bool = False,
):
    _catalog_tasks.load_catalog_snapshot = load_catalog_snapshot
    _catalog_tasks.save_catalog_snapshot = save_catalog_snapshot
    _catalog_tasks.search_catalog = search_catalog
    _catalog_tasks.fetch_label_releases = fetch_label_releases
    _catalog_tasks.fetch_discogs_artist_releases = fetch_discogs_artist_releases
    return _catalog_tasks._fetch_discogs_catalog(
        entity_name,
        token,
        force_refresh=force_refresh,
    )


def _fetch_release_cover_with_discogs(
    release_id: str,
    cache_directory: Path,
    artist: str,
    title: str,
    year: str,
    token: str,
):
    _catalog_tasks._fetch_release_cover = _fetch_release_cover
    _catalog_tasks.search_catalog = search_catalog
    _catalog_tasks._fetch_url_cover = _fetch_url_cover
    return _catalog_tasks._fetch_release_cover_with_discogs(
        release_id,
        cache_directory,
        artist,
        title,
        year,
        token,
    )
