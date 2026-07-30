from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QSettings,
    QSize,
    QThreadPool,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QFontMetrics,
    QKeySequence,
    QPalette,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QInputDialog,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.merger import song_values
from ..diagnostics import get_diagnostic_logger, project_root
from ..history import HistoryManager
from ..library_sources import (
    IndexedAlbum,
    MusicSource,
    load_library_index,
    merge_scan_results,
    save_library_index,
    index_songs,
    update_source_availability,
)
from ..models.song import Song
from ..services.cover import (
    covers_are_identical,
    load_cover,
    load_cover_info,
)
from .. import licensing_keygen as keygen
from .. import usage_limits
from ..licensing import is_feature_enabled, load_license
from ..services.metadata_io import save_song_metadata
from ..services.rename import plan_renames
from ..services.proposal import (
    build_batch_proposals,
    build_proposal,
)
from ..services.auto_tag import (
    DEFAULT_THRESHOLD,
    REASON_LOW_CONFIDENCE,
    run_auto_tag,
    summarize,
)
from ..providers import fingerprint
from ..providers.musicbrainz import (
    MusicBrainzProviderError,
    lookup_recording_by_id,
)
from ..services.scanner import scan_folder_detailed
from ..services.release_text import create_release_text
from ..settings import load_settings, save_settings
from ..i18n import tr, tr_plural
from ..theme import (
    BUTTON_CHANGED,
    BUTTON_NORMAL,
    INPUT_CHANGED,
    INPUT_NORMAL,
    apply_theme,
)
from ..batch_comparison_logic import BatchSongProposal
from .batch_dialog import BatchComparisonDialog
from .about_dialog import AboutDialog
from .comparison_dialog import ComparisonDialog
from .premium_dialog import PremiumDialog
from .settings_dialog import SettingsDialog
from .cover_dialog import (
    CoverSelectionDialog,
    FunctionWorker,
)
from .direct_album_dialog import DirectAlbumDialog
from .audio_analysis_dialog import AudioAnalysisDialog
from .duplicates_dialog import DuplicatesDialog
from .convert_dialog import ConversionDialog
from .now_playing_widget import NowPlayingWidget
from .batch_cover_dialog import BatchCoverDialog
from .library_audit_dialog import LibraryAuditDialog
from .change_preview_dialog import ChangePreviewDialog
from .history_dialog import HistoryDialog
from .media_library_widget import MediaLibraryWidget
from .lyrics_dialog import LyricsDialog
from .lyrics_search_dialog import LyricsSearchDialog
from .dashboard_widget import DashboardWidget
from ..icons import make_icon
from ..player import (
    PlayerBar,
    WindowsMediaKeyController,
    WindowsSystemMediaBridge,
)
from ..cover_management.batch import build_album_cover_plans
from ..cover_management.manager import CoverManager


DEFAULT_MUSIC_FOLDER: str | None = None

COVER_SIZE = 280
MIXED_VALUE_PLACEHOLDER = "<verschiedene Werte>"
OPTIONAL_FIELDS = (
    "isrc",
    "label",
    "copyright",
    "composer",
    "comment",
)


class _LicenseSignals(QObject):
    done = Signal(bool)


class _LicenseCheck(QRunnable):
    """Prüft die Keygen-Lizenz im Hintergrund (Netzwerk blockiert die UI nicht)."""

    def __init__(self, license_key: str, fingerprint: str) -> None:
        super().__init__()
        self._key = license_key
        self._fingerprint = fingerprint
        self.signals = _LicenseSignals()

    def run(self) -> None:
        premium = keygen.refresh_premium(
            self._key,
            self._fingerprint,
            now=datetime.now(),
            cache_path=keygen.default_cache_path(),
        )
        try:
            self.signals.done.emit(premium)
        except RuntimeError:
            # Fenster wurde während der Prüfung geschlossen -> Ergebnis egal.
            pass


def _save_songs_in_parallel(
    items: list[tuple[int, Song]],
) -> list[tuple[int, Song, Exception | None]]:
    """Schreibt mehrere Songs gleichzeitig in ihre Dateien.

    Jeder Song hat einen eigenen Pfad, daher sind die Schreibvorgänge
    unabhängig und lassen sich parallelisieren. Datei-I/O gibt den GIL
    frei, sodass die Wartezeit für ein Album spürbar sinkt. Es findet
    kein Qt-Zugriff statt – die UI-Aktualisierung bleibt beim Aufrufer.
    Ein Fehler pro Datei wird zurückgegeben statt geworfen, damit die
    übrigen Dateien trotzdem gespeichert werden.
    """
    if not items:
        return []

    def _save_one(
        pair: tuple[int, Song],
    ) -> tuple[int, Song, Exception | None]:
        row, updated = pair

        try:
            save_song_metadata(
                updated.path,
                updated,
            )

            return row, updated, None
        except Exception as error:  # noqa: BLE001
            return row, updated, error

    worker_count = min(8, len(items))

    with ThreadPoolExecutor(
        max_workers=worker_count
    ) as pool:
        return list(
            pool.map(_save_one, items)
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MusicTagStudio")
        self.resize(
            1500,
            780,
        )
        self.setMinimumSize(
            860,
            560,
        )

        self.folder: str | None = DEFAULT_MUSIC_FOLDER
        self.current_cover: QPixmap | None = None
        self.songs: list[Song] = []

        self.current_row = -1
        self.active_rows: list[int] = []
        self.previous_rows: list[int] = []

        self.original_values: dict[str, str] = {}
        self.batch_original_values: dict[str, str | None] = {}
        self.batch_touched_fields: set[str] = set()

        self.loading_editor = False
        self.has_unsaved_changes = False
        self.history = HistoryManager(
            project_root()
        )
        self.library_index: list[
            IndexedAlbum
        ] = []
        self.source_scan_worker = None
        self.language = load_settings().language

        # Premium-Status (Keygen) sofort aus dem lokalen Cache vorbelegen, damit
        # die App auch offline direkt richtig gated; danach im Hintergrund
        # aktualisieren.
        self._keygen_premium = keygen.cached_premium(
            load_settings().license_key,
            now=datetime.now(),
            cache_path=keygen.default_cache_path(),
        )
        # Zeitbasierte Testphase beim allerersten Start merken (danach unbegrenzt
        # Premium für TRIAL_DAYS Tage; siehe usage_limits).
        usage_limits.ensure_trial_started(datetime.now())
        # Laufende Lizenz-Hintergrundprüfungen festhalten, damit ihr Ergebnis-
        # Signal nicht durch vorzeitiges Aufräumen verloren geht.
        self._license_workers: set = set()
        # Kulanz-Warnung nur einmal pro Sitzung zeigen.
        self._grace_warned = False

        self.create_ui()
        self.create_menu()
        self.update_history_actions()
        self._refresh_license_async(load_settings().license_key)
        # Lizenz zusätzlich täglich im Hintergrund nachprüfen, damit die
        # Kulanzfrist nie knapp wird und ein Widerruf zeitnah greift.
        self._license_timer = QTimer(self)
        self._license_timer.setInterval(24 * 60 * 60 * 1000)
        self._license_timer.timeout.connect(
            lambda: self._refresh_license_async(load_settings().license_key)
        )
        self._license_timer.start()
        QTimer.singleShot(
            0,
            self.load_configured_sources,
        )

    def create_ui(self):
        container = QWidget()
        container_layout = QVBoxLayout(container)

        left_widget = QWidget()
        self.tagger_left_widget = left_widget
        left_layout = QVBoxLayout(left_widget)

        self.folder_label = QLabel(
            tr("folder_label_single", self.language, path=self.folder)
        )

        self.select_button = QPushButton(
            tr("music_folder", self.language)
        )
        self.select_button.clicked.connect(self.select_folder)

        self.scan_button = QPushButton(
            tr("library_rescan", self.language)
        )
        self.scan_button.clicked.connect(self.rescan_library)

        self.provider_buttons_layout = QGridLayout()

        self.proposal_button = QPushButton(
            tr("search_metadata_title", self.language)
        )
        self.proposal_button.setToolTip(tr("search_metadata_title", self.language))
        self.proposal_button.clicked.connect(
            self.create_single_proposal
        )
        self.proposal_button.setEnabled(False)

        self.identify_button = QPushButton(
            tr("identify_by_sound", self.language)
        )
        self.identify_button.setToolTip(
            tr("identify_by_sound_tip", self.language)
        )
        self.identify_button.clicked.connect(
            self.identify_by_sound
        )
        self.identify_button.setEnabled(False)

        self.batch_button = QPushButton(
            tr("search_metadata_selection", self.language)
        )
        self.batch_button.setToolTip(tr("search_metadata_selection", self.language))
        self.batch_button.clicked.connect(
            self.create_batch_proposals
        )
        self.batch_button.setEnabled(False)

        self.auto_tag_button = QPushButton(
            tr("auto_tag", self.language)
        )
        self.auto_tag_button.setToolTip(tr("auto_tag_tip", self.language))
        self.auto_tag_button.clicked.connect(self.auto_tag_selected)
        self.auto_tag_button.setEnabled(False)

        self.convert_button = QPushButton(
            tr("convert", self.language)
        )
        self.convert_button.setToolTip(tr("convert_tip", self.language))
        self.convert_button.clicked.connect(self.convert_selected)
        self.convert_button.setEnabled(False)

        self.cover_button = QPushButton(
            tr("manage_cover_selection", self.language)
        )
        self.cover_button.setToolTip(tr("manage_cover_selection", self.language))
        self.cover_button.clicked.connect(
            self.manage_cover
        )
        self.cover_button.setEnabled(False)

        self.lyrics_button = QPushButton(tr("show_lyrics", self.language))
        self.lyrics_button.setToolTip(
            tr("show_lyrics_tip", self.language)
        )
        self.lyrics_button.clicked.connect(self.show_lyrics)
        self.lyrics_button.setEnabled(False)

        self.lyrics_search_button = QPushButton(tr("lyrics_search", self.language))
        self.lyrics_search_button.setToolTip(
            tr("lyrics_search_tip", self.language)
        )
        self.lyrics_search_button.clicked.connect(self.search_song_by_lyrics)

        self.player_button = QPushButton(tr("play_track", self.language))
        self.player_button.setToolTip(tr("play_track_tip", self.language))
        self.player_button.clicked.connect(self.play_selected_song)
        self.player_button.setEnabled(False)

        self.direct_album_button = QPushButton(
            tr("load_direct", self.language)
        )
        self.direct_album_button.setToolTip(
            tr("load_direct_tip", self.language)
        )
        self.direct_album_button.clicked.connect(
            self.load_direct_album
        )
        self.direct_album_button.setEnabled(False)

        self.release_text_button = QPushButton(
            tr("create_bbcode", self.language)
        )
        self.release_text_button.setToolTip(tr("create_bbcode", self.language))
        self.release_text_button.clicked.connect(
            self.create_release_text_file
        )
        self.release_text_button.setEnabled(False)

        self.more_artist_button = QPushButton(
            tr("more_artist", self.language)
        )
        self.more_artist_button.setToolTip(
            tr("more_artist_tip", self.language)
        )
        self.more_artist_button.clicked.connect(
            self.show_more_from_artist
        )
        self.more_artist_button.setEnabled(
            False
        )


        self.table_fields = (
            "track",
            "title",
            "artist",
            "album",
            "disc",
            "year",
            "isrc",
            "label",
            "copyright",
            "composer",
            "comment",
            "path",
        )

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.table_fields))
        self.table.setHorizontalHeaderLabels(
            [
                tr("col_track", self.language),
                tr("col_title", self.language),
                tr("col_artist", self.language),
                tr("col_album", self.language),
                tr("col_disc", self.language),
                tr("col_year", self.language),
                tr("col_isrc", self.language),
                tr("col_label", self.language),
                tr("col_copyright", self.language),
                tr("col_composer", self.language),
                tr("col_comment", self.language),
                tr("col_file", self.language),
            ]
        )

        self.table.itemSelectionChanged.connect(
            self.handle_selection_changed
        )
        self.table.cellDoubleClicked.connect(
            lambda row, _column: self.play_song_row(row)
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        header = self.table.horizontalHeader()
        header.setSectionsMovable(False)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(45)

        for index in range(
            len(self.table_fields)
        ):
            header.setSectionResizeMode(
                index,
                QHeaderView.ResizeMode.Interactive,
            )

        self._column_settings = QSettings(
            "MusicTagStudio",
            "MusicTagStudio",
        )
        self._restoring_column_widths = False
        self._restore_table_column_widths()
        header.sectionResized.connect(
            self._save_table_column_widths
        )

        history_buttons = QHBoxLayout()
        history_icon_color = self.palette().color(
            QPalette.ColorRole.ButtonText
        ).name()
        self.undo_button = QPushButton(
            tr("undo", self.language)
        )
        self.undo_button.setIcon(make_icon("undo", history_icon_color))
        self.undo_button.clicked.connect(
            self.undo_last_change
        )
        self.redo_button = QPushButton(
            tr("redo", self.language)
        )
        self.redo_button.setIcon(make_icon("redo", history_icon_color))
        self.redo_button.clicked.connect(
            self.redo_last_change
        )
        self.history_button = QPushButton(
            tr("history", self.language)
        )
        self.history_button.clicked.connect(
            self.show_history
        )
        history_buttons.addWidget(
            self.undo_button
        )
        history_buttons.addWidget(
            self.redo_button
        )
        history_buttons.addWidget(
            self.history_button
        )

        left_layout.addWidget(self.folder_label)
        library_actions = QHBoxLayout()
        library_actions.addWidget(self.select_button, 1)
        library_actions.addWidget(self.scan_button, 1)
        library_actions.addWidget(self.direct_album_button, 1)
        left_layout.addLayout(library_actions)
        self.provider_action_buttons = (
            self.proposal_button,
            self.identify_button,
            self.batch_button,
            self.auto_tag_button,
            self.convert_button,
            self.cover_button,
            self.lyrics_button,
            self.player_button,
            self.release_text_button,
            self.more_artist_button,
        )
        left_layout.addLayout(
            self.provider_buttons_layout
        )
        self._layout_provider_buttons(
        )
        left_layout.addLayout(history_buttons)
        left_layout.addLayout(self._build_filter_bar())
        left_layout.addWidget(self.table)

        right_widget = QWidget()
        right_widget.setMinimumWidth(
            300
        )
        right_widget.setMaximumWidth(
            560
        )
        right_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        right_layout = QVBoxLayout(right_widget)

        self.selection_label = QLabel(
            tr("no_track_selected", self.language)
        )
        self.selection_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        right_layout.addWidget(self.selection_label)

        self.cover_label = QLabel(tr("no_cover", self.language))
        self.cover_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.cover_label.setFixedSize(
            COVER_SIZE,
            COVER_SIZE,
        )
        self.cover_label.setStyleSheet(
            "QLabel {"
            " border: 1px solid palette(mid);"
            " border-radius: 4px;"
            " padding: 6px;"
            "}"
        )

        right_layout.addWidget(
            self.cover_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setVerticalSpacing(8)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.editor_fields: dict[str, QLineEdit] = {}

        labels = {
            name: tr(f"field_{name}", self.language) + ":"
            for name in (
                "title",
                "artist",
                "album_artist",
                "album",
                "genre",
                "year",
                "isrc",
                "label",
                "copyright",
                "composer",
                "comment",
            )
        }

        for name in (
            "title",
            "artist",
            "album_artist",
            "album",
            "genre",
            "year",
        ):
            field = QLineEdit()
            self.editor_fields[name] = field
            form.addRow(labels[name], field)

        for prefix, first, second in (
            ("Track:", "track", "total_tracks"),
            ("Disc:", "disc", "total_discs"),
        ):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            first_edit = QLineEdit()
            second_edit = QLineEdit()

            self.editor_fields[first] = first_edit
            self.editor_fields[second] = second_edit

            row_layout.addWidget(first_edit)
            row_layout.addWidget(QLabel("/"))
            row_layout.addWidget(second_edit)

            form.addRow(prefix, row_widget)

        for name in OPTIONAL_FIELDS:
            field = QLineEdit()
            self.editor_fields[name] = field
            form.addRow(labels[name], field)

        self.save_button = QPushButton(BUTTON_NORMAL)
        self.save_button.clicked.connect(self.save_song)
        self.save_button.setEnabled(False)
        form.addRow(self.save_button)

        for name, field in self.editor_fields.items():
            field.textEdited.connect(
                lambda _text, field_name=name:
                self.mark_field_edited(field_name)
            )
            field.textChanged.connect(
                self.update_dirty_state
            )

        self.editor_scroll = QScrollArea()
        self.editor_scroll.setWidgetResizable(True)
        self.editor_scroll.setFrameShape(
            QScrollArea.Shape.NoFrame
        )
        self.editor_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.editor_scroll.setWidget(form_widget)
        right_layout.addWidget(
            self.editor_scroll,
            stretch=1,
        )

        self.splitter = QSplitter(
            Qt.Orientation.Horizontal
        )
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setChildrenCollapsible(
            False
        )
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        saved_splitter_sizes = self._column_settings.value(
            "main/splitter_sizes", [1080, 420]
        )
        try:
            splitter_sizes = [int(value) for value in saved_splitter_sizes]
        except (TypeError, ValueError):
            splitter_sizes = [1080, 420]
        self.splitter.setSizes(splitter_sizes)
        self.splitter.splitterMoved.connect(
            lambda *_: self._column_settings.setValue(
                "main/splitter_sizes", self.splitter.sizes()
            )
        )

        container_layout.addWidget(self.splitter)

        self.workspace_stack = QStackedWidget()
        self.workspace_stack.setMinimumWidth(
            0
        )
        self.workspace_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.workspace_stack.addWidget(
            container
        )

        self.media_library = MediaLibraryWidget(
            self
        )
        self.media_library.open_local_album.connect(
            self.open_local_album_from_library
        )
        self.media_library.play_local_tracks.connect(
            self._play_media_library_tracks
        )
        self.media_library.enqueue_local_tracks.connect(
            self._enqueue_media_library_tracks
        )
        self.workspace_stack.addWidget(
            self.media_library
        )

        self.audio_analysis_workspace = AudioAnalysisDialog(
            [],
            [],
            self,
            embedded=True,
            language=self.language,
        )
        self.workspace_stack.addWidget(
            self.audio_analysis_workspace
        )

        self.library_audit_workspace = LibraryAuditDialog(
            [],
            [],
            self,
            embedded=True,
            language=self.language,
        )
        self.workspace_stack.addWidget(
            self.library_audit_workspace
        )

        self.settings_workspace = SettingsDialog(
            load_settings(),
            self,
            embedded=True,
        )
        self.settings_workspace.settings_saved.connect(
            self.apply_embedded_settings
        )
        self.workspace_stack.addWidget(
            self.settings_workspace
        )

        self.dashboard_workspace = DashboardWidget(
            self,
            language=self.language,
        )
        self.dashboard_workspace.open_workspace.connect(
            self.switch_workspace
        )
        self.dashboard_workspace.refresh_requested.connect(
            self.scan_configured_sources
        )
        self.workspace_stack.addWidget(
            self.dashboard_workspace
        )

        self.duplicates_workspace = DuplicatesDialog(
            [],
            self,
            embedded=True,
            language=self.language,
        )
        self.duplicates_workspace.songs_deleted.connect(
            self._on_duplicates_deleted
        )
        self.workspace_stack.addWidget(
            self.duplicates_workspace
        )

        sidebar = QWidget()
        sidebar.setObjectName(
            "mainSidebar"
        )
        sidebar.setStyleSheet(
            """
            QWidget#mainSidebar {
                border-right: 1px solid palette(mid);
                background: palette(base);
            }
            """
        )
        sidebar_layout = QVBoxLayout(
            sidebar
        )
        sidebar_layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )
        sidebar_layout.setSpacing(5)
        brand = QLabel(
            "MusicTagStudio"
        )
        brand.setStyleSheet(
            "font-size: 18px; font-weight: 600;"
        )
        sidebar_layout.addWidget(
            brand
        )

        self.workspace_buttons = QButtonGroup(
            self
        )
        self.workspace_buttons.setExclusive(
            True
        )
        # (i18n-Key, Workspace-Index, Icon-Name)
        workspace_pages = (
            ("home", 5, "nav_home"),
            ("tagger", 0, "nav_tagger"),
            ("media_library", 1, "nav_library"),
            ("audio_analysis", 2, "nav_analysis"),
            ("library_audit", 3, "nav_audit"),
            ("duplicates", 6, "nav_duplicates"),
            ("playback", 7, "nav_play"),
        )

        nav_color = self.palette().color(
            QPalette.ColorRole.ButtonText
        ).name()
        for name, index, icon_name in workspace_pages:
            button = QPushButton(
                tr(name, self.language)
            )
            button.setIcon(make_icon(icon_name, nav_color))
            button.setIconSize(QSize(18, 18))
            button.setStyleSheet("text-align: left; padding-left: 8px;")
            button.setCheckable(
                True
            )
            button.setMinimumHeight(
                34
            )
            button.clicked.connect(
                lambda _checked=False, page=index:
                self.switch_workspace(
                    page
                )
            )
            self.workspace_buttons.addButton(
                button,
                index,
            )
            sidebar_layout.addWidget(
                button
            )

        # Aktions-Knopf (kein Workspace) unter der Navigation.
        self.lyrics_search_button.setMinimumHeight(34)
        self.lyrics_search_button.setIcon(make_icon("nav_lyrics", nav_color))
        self.lyrics_search_button.setIconSize(QSize(18, 18))
        self.lyrics_search_button.setStyleSheet(
            "text-align: left; padding-left: 8px;"
        )
        sidebar_layout.addWidget(
            self.lyrics_search_button
        )

        # Sidebar-Breite an den laengsten Buttontext anpassen (Sprache + evtl.
        # groessere Schrift), statt eine feste Pixelzahl zu erzwingen. So laeuft
        # kein Label ueber und schmale Sprachen verschwenden keinen Platz.
        self._sidebar = sidebar
        self._sidebar_nav_keys = [name for name, _index, _icon in workspace_pages]
        self._sidebar_nav_keys.append("lyrics_search")
        self._adjust_sidebar_width()

        sidebar_layout.addStretch()

        shell = QWidget()
        shell.setMinimumWidth(
            0
        )
        shell_layout = QHBoxLayout(
            shell
        )
        shell_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        shell_layout.addWidget(
            sidebar
        )
        shell_layout.addWidget(
            self.workspace_stack,
            stretch=1,
        )
        self.player_bar = PlayerBar(self)
        # Favoriten + Hör-Statistik (lokal persistiert) an die Engine koppeln.
        from ..services.favorites import Favorites, default_favorites_path
        from ..services.listening_stats import (
            ListeningStats,
            default_stats_path,
        )

        self.favorites = Favorites(default_favorites_path())
        self.listening_stats = ListeningStats(default_stats_path())
        self._listen_started: float | None = None
        self._listen_song: Song | None = None
        self._listen_playing = False
        self.player_bar.engine.playback_changed.connect(
            self._on_playback_for_stats
        )
        self.player_bar.engine.song_changed.connect(self._on_song_for_stats)
        # Wiedergabe-Großansicht (Cover/Infos/BPM/Steuerung) an dieselbe Engine
        # binden und als Workspace (Index 7) hinzufügen.
        self.now_playing_workspace = NowPlayingWidget(
            self.player_bar.engine,
            self,
            language=self.language,
            favorites=self.favorites,
        )
        self.now_playing_workspace.detach_requested.connect(
            self._detach_now_playing
        )
        self.now_playing_workspace.stats_requested.connect(
            self._show_listening_stats
        )
        self.workspace_stack.addWidget(self.now_playing_workspace)
        # Die untere Leiste spiegelt zusätzlich die Track-Vorschau der
        # Medienbibliothek (Titel, Position, ~30 Sek.), ohne die lokale
        # Wiedergabe zu verändern.
        self.player_bar.bind_preview_player(
            self.media_library.preview_player
        )
        self.windows_media_keys = WindowsMediaKeyController(
            self.player_bar.engine
        )
        self.windows_media_keys.start(int(self.winId()))
        self.windows_system_media = WindowsSystemMediaBridge(
            self.player_bar.engine,
            self,
        )
        if self.windows_system_media.start():
            # SMTC receives the same hardware buttons and must be the single
            # handler; otherwise Play/Pause could be executed twice.
            self.windows_media_keys.stop()
        self.player_bar.engine.song_changed.connect(
            self._player_song_changed
        )
        # Einheitlicher Fehlerkanal: transiente Player-Meldungen in der
        # Statusleiste anzeigen (statt im Titel-Label).
        self.player_bar.status_requested.connect(
            self._show_player_status
        )
        # Gespeicherte Warteschlange wiederherstellen (pausiert). Bewusst erst
        # hier, damit direkt konstruierte PlayerBar-Instanzen (z. B. in Tests)
        # nicht die echte Ablage lesen.
        self.player_bar.restore_queue()
        self.play_pause_shortcut = QShortcut(
            QKeySequence(Qt.Key.Key_Space),
            self,
        )
        self.play_pause_shortcut.activated.connect(
            self._toggle_player_from_shortcut
        )
        application_shell = QWidget()
        application_layout = QVBoxLayout(application_shell)
        application_layout.setContentsMargins(0, 0, 0, 0)
        application_layout.setSpacing(0)
        application_layout.addWidget(shell, stretch=1)
        application_layout.addWidget(self.player_bar)
        self.setCentralWidget(application_shell)
        self.switch_workspace(
            5
        )

        self.update_optional_columns()

    def switch_workspace(
        self,
        index: int,
    ) -> None:
        if index in {
            2,
            3,
        }:
            selected_rows = self.selected_rows()
            selected_songs = [
                self.songs[row]
                for row in selected_rows
                if 0 <= row < len(self.songs)
            ]

            if index == 2:
                self.audio_analysis_workspace.set_songs(
                    selected_songs,
                    self.songs,
                )
            else:
                self.library_audit_workspace.set_songs(
                    selected_songs,
                    self.songs,
                )

        if index == 6:
            self.duplicates_workspace.set_songs(self.songs)

        self.workspace_stack.setCurrentIndex(
            index
        )
        if index == 5:
            settings = load_settings()
            self.library_index = update_source_availability(
                load_library_index(),
                settings.music_sources,
            )
            self.dashboard_workspace.update_library(
                self.library_index,
                settings.music_sources,
            )
        names = {
            0: "tagger",
            1: "media_library",
            2: "audio_analysis",
            3: "library_audit",
            4: "settings_page",
            5: "home",
        }
        self.statusBar().showMessage(
            tr(names.get(index, "ready"), self.language)
        )
        button = self.workspace_buttons.button(
            index
        )

        if button is not None:
            button.setChecked(
                True
            )
        else:
            checked_button = self.workspace_buttons.checkedButton()
            if checked_button is not None:
                self.workspace_buttons.setExclusive(False)
                checked_button.setChecked(False)
                self.workspace_buttons.setExclusive(True)

    def _adjust_sidebar_width(self) -> None:
        # Breite = breitester Nav-Text (in aktueller Schrift) + Icon/Padding.
        # Die App-Schrift ist massgeblich (spiegelt eine gerade geaenderte
        # Schriftgroesse sofort, ohne auf einen Event-Loop zu warten).
        app = QApplication.instance()
        font = app.font() if isinstance(app, QApplication) else self._sidebar.font()
        metrics = QFontMetrics(font)
        widest_text = max(
            metrics.horizontalAdvance(tr(key, self.language))
            for key in self._sidebar_nav_keys
        )
        # Icon (18) + Icon-Abstand + linkes Padding (8) + Layout-Raender (2x8)
        # + etwas Luft rechts, damit nichts an der Trennlinie klebt.
        self._sidebar.setFixedWidth(max(180, widest_text + 78))

    def apply_embedded_settings(
        self,
        new_settings,
    ) -> None:
        save_settings(
            new_settings
        )
        self.language = new_settings.language
        self.media_library.language = new_settings.language
        # Lizenzstatus nach dem Speichern neu ermitteln (Key evtl. geändert):
        # sofort aus dem Cache, dann im Hintergrund online verifizieren.
        self._keygen_premium = keygen.cached_premium(
            new_settings.license_key,
            now=datetime.now(),
            cache_path=keygen.default_cache_path(),
        )
        self._refresh_license_async(new_settings.license_key)
        app = QApplication.instance()

        if isinstance(app, QApplication):
            # Theme + Schriftgroesse zusammen anwenden: apply_theme skaliert die
            # font-size im Stylesheet mit, damit die Auswahl ohne Neustart
            # sichtbar wird; Sidebar danach an die neue Schrift anpassen.
            apply_theme(
                app,
                new_settings.theme,
                new_settings.theme_style,
                new_settings.font_scale,
            )
            self._adjust_sidebar_width()

        self.load_configured_sources()
        self.statusBar().showMessage(
            "Einstellungen gespeichert",
            4000,
        )

    def open_local_album_from_library(
        self,
        folder: str,
    ) -> None:
        self.folder = folder
        self.folder_label.setText(
            tr("folder_label_single", self.language, path=folder)
        )
        self.switch_workspace(
            0
        )
        self.scan_music()

    def _default_table_column_widths(
        self,
    ) -> dict[str, int]:
        return {
            "track": 72,
            "title": 230,
            "artist": 230,
            "album": 220,
            "disc": 65,
            "year": 65,
            "label": 120,
            "copyright": 170,
            "composer": 160,
            "comment": 220,
            "path": 300,
        }

    def _restore_table_column_widths(
        self,
    ) -> None:
        defaults = self._default_table_column_widths()
        stored = self._column_settings.value(
            "main_table/column_widths",
            "",
        )
        widths: list[int] = []

        if isinstance(stored, str):
            try:
                widths = [
                    int(value)
                    for value in stored.split(",")
                    if value.strip()
                ]
            except ValueError:
                widths = []

        self._restoring_column_widths = True

        try:
            for index, field_name in enumerate(
                self.table_fields
            ):
                width = (
                    widths[index]
                    if index < len(widths)
                    and widths[index] >= 45
                    else defaults.get(field_name, 110)
                )
                self.table.setColumnWidth(index, width)
        finally:
            self._restoring_column_widths = False

    def _save_table_column_widths(
        self,
        _logical_index: int,
        _old_size: int,
        _new_size: int,
    ) -> None:
        if self._restoring_column_widths:
            return

        widths = [
            self.table.columnWidth(index)
            for index in range(
                self.table.columnCount()
            )
        ]
        self._column_settings.setValue(
            "main_table/column_widths",
            ",".join(str(width) for width in widths),
        )

    def reset_table_column_widths(
        self,
    ) -> None:
        self._column_settings.remove(
            "main_table/column_widths"
        )
        self._restore_table_column_widths()

    def _layout_provider_buttons(
        self,
    ) -> None:
        while self.provider_buttons_layout.count():
            item = self.provider_buttons_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(self.provider_buttons_layout.parentWidget())

        # Jeder Knopf trägt seinen Text/Tooltip bereits von der Erstellung –
        # hier wird nur noch angeordnet (keine positionsbasierte Umbenennung,
        # die beim Hinzufügen eines Knopfes alles verschieben würde).
        columns = 4
        for index, button in enumerate(self.provider_action_buttons):
            self.provider_buttons_layout.addWidget(
                button,
                index // columns,
                index % columns,
            )

    def resizeEvent(
        self,
        event,
    ) -> None:
        super().resizeEvent(
            event
        )

    def create_menu(self):
        file_menu = self.menuBar().addMenu(
            tr("file", self.language)
        )

        add_folder_action = QAction(
            tr("add_folder", self.language),
            self,
        )
        add_folder_action.setShortcut(
            QKeySequence(
                "Ctrl+O"
            )
        )
        add_folder_action.setStatusTip(
            tr("shortcut_add_folder", self.language)
        )
        add_folder_action.triggered.connect(
            self.select_folder
        )
        file_menu.addAction(
            add_folder_action
        )

        rescan_action = QAction(
            tr("rescan", self.language),
            self,
        )
        rescan_action.setShortcut(
            QKeySequence(
                "F5"
            )
        )
        rescan_action.triggered.connect(
            self.scan_music
        )
        file_menu.addAction(
            rescan_action
        )

        file_menu.addSeparator()

        settings_action = QAction(
            tr("settings", self.language),
            self,
        )
        settings_action.setShortcut(
            QKeySequence(
                "Ctrl+,"
            )
        )
        settings_action.setStatusTip(
            tr("shortcut_settings", self.language)
        )
        settings_action.triggered.connect(
            lambda: self.switch_workspace(
                4
            )
        )
        file_menu.addAction(
            settings_action
        )

        file_menu.addSeparator()

        exit_action = QAction(
            tr("exit", self.language),
            self,
        )
        exit_action.setShortcut(
            QKeySequence.StandardKey.Quit
        )
        exit_action.triggered.connect(
            self.close
        )
        file_menu.addAction(
            exit_action
        )

        edit_menu = self.menuBar().addMenu(
            tr("edit", self.language)
        )
        self.undo_action = QAction(
            tr("undo", self.language),
            self,
        )
        self.undo_action.setShortcut(
            QKeySequence.StandardKey.Undo
        )
        self.undo_action.triggered.connect(
            self.undo_last_change
        )
        edit_menu.addAction(
            self.undo_action
        )

        self.redo_action = QAction(
            tr("redo", self.language),
            self,
        )
        self.redo_action.setShortcuts(
            [
                QKeySequence.StandardKey.Redo,
                QKeySequence(
                    "Ctrl+Y"
                ),
            ]
        )
        self.redo_action.triggered.connect(
            self.redo_last_change
        )
        edit_menu.addAction(
            self.redo_action
        )

        history_action = edit_menu.addAction(
            tr("history", self.language)
        )
        history_action.triggered.connect(
            self.show_history
        )

        edit_menu.addSeparator()
        rename_action = edit_menu.addAction(
            tr("rename_action", self.language)
        )
        rename_action.triggered.connect(
            self.rename_files
        )

        edit_menu.addSeparator()
        reset_columns_action = edit_menu.addAction(
            tr("reset_columns", self.language)
        )
        reset_columns_action.triggered.connect(
            self.reset_table_column_widths
        )

        info_menu = self.menuBar().addMenu(tr("info", self.language))
        about_action = info_menu.addAction(tr("about", self.language))
        about_action.triggered.connect(self.show_about_dialog)

    def show_about_dialog(self) -> None:
        premium = self._premium_active(load_settings())
        AboutDialog(self, language=self.language, premium=premium).exec()

    def _selected_album_artist(
        self,
    ) -> str:
        rows = self.selected_rows()

        if not rows:
            return ""

        artists = {
            (
                self.songs[row].album_artist
                or self.songs[row].artist
            ).strip()
            for row in rows
            if 0 <= row < len(
                self.songs
            )
        }
        artists.discard(
            ""
        )

        if len(artists) != 1:
            return ""

        return next(
            iter(
                artists
            )
        )

    def _update_more_artist_button(
        self,
    ) -> None:
        artist = (
            self._selected_album_artist()
        )
        self.more_artist_button.setEnabled(
            bool(
                artist
            )
        )
        self.more_artist_button.setToolTip(
            tr("discography_of", self.language, artist=artist)
            if artist
            else tr("more_artist_hint", self.language)
        )

    def show_more_from_artist(
        self,
    ) -> None:
        artist = (
            self._selected_album_artist()
        )

        if not artist:
            return

        self.switch_workspace(
            1
        )
        self.media_library.search_artist(
            artist
        )

    def _selected_album_keys(
        self,
        rows: list[int] | None = None,
    ) -> set[tuple[str, str, str]]:
        selected = (
            self.selected_rows()
            if rows is None
            else rows
        )

        return {
            (
                (
                    self.songs[row].album_artist
                    or self.songs[row].artist
                ).strip().casefold(),
                self.songs[row].album.strip().casefold(),
                str(
                    Path(
                        self.songs[row].path
                    ).parent.resolve()
                ).casefold(),
            )
            for row in selected
            if 0 <= row < len(
                self.songs
            )
        }

    def _update_release_text_button(
        self,
    ) -> None:
        rows = self.selected_rows()
        album_keys = (
            self._selected_album_keys(
                rows
            )
            if rows
            else set()
        )
        enabled = (
            bool(rows)
            and len(album_keys) == 1
        )
        self.release_text_button.setEnabled(
            enabled
        )

        if not rows:
            tooltip = tr("release_hint_none", self.language)
        elif len(album_keys) > 1:
            tooltip = tr("release_hint_multi", self.language)
        else:
            tooltip = tr("release_hint_ok", self.language)

        self.release_text_button.setToolTip(
            tooltip
        )

    def _update_lyrics_button(self) -> None:
        rows = self.selected_rows()
        enabled = len(rows) == 1 and 0 <= rows[0] < len(self.songs)
        self.lyrics_button.setEnabled(enabled)
        self.lyrics_button.setToolTip(
            tr("lyrics_enabled_hint", self.language)
            if enabled
            else tr("select_one_track", self.language)
        )
        self.player_button.setEnabled(enabled)
        self.player_button.setToolTip(
            tr("play_track_tip", self.language)
            if enabled
            else tr("select_one_track", self.language)
        )

    def play_selected_song(self) -> None:
        rows = self.selected_rows()
        if len(rows) == 1:
            self.play_song_row(rows[0])

    def play_song_row(self, row: int) -> None:
        if not (0 <= row < len(self.songs)):
            return
        if not self.player_bar.play_songs(self.songs, row):
            self.statusBar().showMessage(
                tr("audio_unreachable", self.language),
                5000,
            )
            return
        song = self.songs[row]
        self.statusBar().showMessage(
            tr(
                "playing",
                self.language,
                title=song.title or Path(song.path).name,
            ),
            3000,
        )

    def _play_media_library_tracks(
        self,
        songs: list[Song],
        start_index: int,
    ) -> None:
        if not self.player_bar.play_songs(songs, start_index):
            self.statusBar().showMessage(
                tr("audio_unreachable", self.language),
                5000,
            )
            return
        song = songs[start_index]
        self.statusBar().showMessage(
            tr(
                "playing",
                self.language,
                title=song.title or Path(song.path).name,
            ),
            3000,
        )

    def _enqueue_media_library_tracks(self, songs: list[Song]) -> None:
        count = self.player_bar.engine.enqueue_songs(songs)
        self.statusBar().showMessage(
            tr("enqueued", self.language, count=count),
            4000,
        )

    def _toggle_player_from_shortcut(self) -> None:
        focus = QApplication.focusWidget()
        if focus is not None and (
            focus.inherits("QLineEdit")
            or focus.inherits("QTextEdit")
            or focus.inherits("QPlainTextEdit")
        ):
            return
        self.player_bar.engine.toggle()

    def _player_song_changed(self, song: Song | None) -> None:
        if song is None:
            return
        wanted_path = str(Path(song.path)).casefold()
        for row, candidate in enumerate(self.songs):
            if str(Path(candidate.path)).casefold() == wanted_path:
                self.table.selectRow(row)
                item = self.table.item(row, 0)
                if item is not None:
                    self.table.scrollToItem(item)
                break
        self.media_library.highlight_playing_song(song)

    def show_lyrics(self) -> None:
        rows = self.selected_rows()
        if len(rows) != 1 or not (0 <= rows[0] < len(self.songs)):
            return
        dialog = LyricsDialog(
            self.songs[rows[0]],
            self,
            player_engine=self.player_bar.engine,
            language=self.language,
        )
        dialog.exec()

    def search_song_by_lyrics(self) -> None:
        dialog = LyricsSearchDialog(
            tuple(self.songs),
            self,
            player_bar=self.player_bar,
            language=self.language,
        )
        dialog.exec()

    def create_release_text_file(
        self,
    ):
        rows = self.selected_rows()

        if not rows:
            return

        selected_songs = [
            self.songs[row]
            for row in rows
        ]
        album_keys = self._selected_album_keys(
            rows
        )

        if len(album_keys) != 1:
            QMessageBox.warning(
                self,
                tr("release_multi_album_title", self.language),
                tr("release_multi_album_msg", self.language),
            )
            return

        self.release_text_button.setEnabled(
            False
        )
        self.release_text_button.setText(
            tr("creating_release_text", self.language)
        )
        settings = load_settings()
        worker = FunctionWorker(
            create_release_text,
            selected_songs,
            settings,
        )

        def finished(
            result,
        ):
            self.release_text_button.setText(
                tr("create_bbcode", self.language)
            )
            self._update_release_text_button()
            QMessageBox.information(
                self,
                tr("release_saved_title", self.language),
                tr(
                    "release_saved_msg",
                    self.language,
                    path=result.path,
                    analyzed=result.analyzed_files,
                    total=result.total_files,
                ),
            )

        def failed(
            message: str,
        ):
            self.release_text_button.setText(
                tr("create_bbcode", self.language)
            )
            self._update_release_text_button()
            QMessageBox.critical(
                self,
                tr("release_failed_title", self.language),
                message,
            )

        worker.signals.finished.connect(
            finished
        )
        worker.signals.failed.connect(
            failed
        )
        self._release_text_worker = worker
        QThreadPool.globalInstance().start(
            worker
        )

    def update_history_actions(
        self,
    ):
        can_undo = (
            self.history.can_undo
        )
        can_redo = (
            self.history.can_redo
        )
        self.undo_button.setEnabled(
            can_undo
        )
        self.redo_button.setEnabled(
            can_redo
        )

        if hasattr(
            self,
            "undo_action",
        ):
            self.undo_action.setEnabled(
                can_undo
            )
            self.redo_action.setEnabled(
                can_redo
            )

    def undo_last_change(self):
        entry = self.history.undo()

        if entry is None:
            return

        self.scan_music()
        self.update_history_actions()
        QMessageBox.information(
            self,
            tr("undo", self.language),
            tr(
                "undo_done_msg",
                self.language,
                description=tr(entry.description, self.language),
            ),
        )

    def redo_last_change(self):
        entry = self.history.redo()

        if entry is None:
            return

        self.scan_music()
        self.update_history_actions()
        QMessageBox.information(
            self,
            tr("redone_title", self.language),
            tr(
                "redo_done_msg",
                self.language,
                description=tr(entry.description, self.language),
            ),
        )

    def show_history(self):
        HistoryDialog(
            self.history.entries(),
            self,
            language=self.language,
            describe=self.history.describe_changes,
        ).exec()

    def _preview_changes(
        self,
        items: list[
            tuple[int, Song]
        ],
    ) -> bool:
        field_labels = {
            name: tr(f"field_{name}", self.language)
            for name in (
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
        }
        changes: list[
            tuple[str, str, str, str]
        ] = []
        changed_rows: set[int] = set()

        for row, updated in items:
            original = self.songs[
                row
            ]

            for name, label in (
                field_labels.items()
            ):
                before = str(
                    getattr(
                        original,
                        name,
                        "",
                    )
                    or ""
                )
                after = str(
                    getattr(
                        updated,
                        name,
                        "",
                    )
                    or ""
                )

                if before != after:
                    changes.append(
                        (
                            original.title
                            or Path(
                                original.path
                            ).name,
                            label,
                            before,
                            after,
                        )
                    )
                    changed_rows.add(row)

        if not changes:
            return True

        return (
            ChangePreviewDialog(
                changes,
                self,
                file_count=len(changed_rows),
                language=self.language,
            ).exec()
            == ChangePreviewDialog.DialogCode.Accepted
        )

    def _write_song_updates(
        self,
        description_key: str,
        items: list[
            tuple[int, Song]
        ],
    ) -> tuple[int, list[str]]:
        if not items:
            return 0, []

        # Abgeschaltete Tag-Felder nicht überschreiben: für sie den bisherigen
        # Wert der Datei beibehalten (Einstellung "Eingebettete Tags").
        disabled = load_settings().disabled_tag_fields
        if disabled:
            items = [
                (
                    row,
                    replace(
                        updated,
                        **{
                            field: getattr(self.songs[row], field)
                            for field in disabled
                            if hasattr(updated, field)
                        },
                    ),
                )
                for row, updated in items
            ]

        if not self._preview_changes(
            items
        ):
            return 0, []

        # Der Verlauf speichert den i18n-Key (nicht den uebersetzten Text),
        # damit ein Sprachwechsel auch alte Eintraege korrekt anzeigt.
        entry = self.history.begin(
            description_key,
            [
                updated.path
                for _row, updated
                in items
            ],
        )
        saved = 0
        failed: list[str] = []

        try:
            # Die Dateien werden parallel geschrieben (I/O gibt den GIL frei),
            # die UI-Aktualisierung bleibt danach auf dem Hauptthread.
            for row, updated, error in _save_songs_in_parallel(
                items
            ):
                if error is not None:
                    failed.append(
                        f"{updated.title}: {error}"
                    )
                    continue

                self.songs[row] = (
                    updated
                )
                self.update_table_row(
                    row,
                    updated,
                )
                saved += 1

            if saved:
                self.history.commit(
                    entry
                )
            else:
                self.history.rollback_pending(
                    entry
                )
        except Exception:
            self.history.rollback_pending(
                entry
            )
            raise
        finally:
            self.update_history_actions()

        return saved, failed

    def _refresh_license_async(self, license_key: str) -> None:
        """Startet die Keygen-Prüfung im Hintergrund und aktualisiert den Status."""
        from ..licensing import machine_fingerprint

        if not license_key.strip() or not keygen.is_configured():
            self._keygen_premium = False
            return
        worker = _LicenseCheck(license_key, machine_fingerprint())
        worker.setAutoDelete(False)
        self._license_workers.add(worker)
        worker.signals.done.connect(
            lambda premium, w=worker: self._on_license_checked(premium, w)
        )
        QThreadPool.globalInstance().start(worker)

    def _on_license_checked(self, premium: bool, worker) -> None:
        self._set_keygen_premium(premium)
        self._license_workers.discard(worker)
        # Läuft Premium nur noch über die Kulanzfrist (seit >= 10 Tagen offline),
        # einmal pro Sitzung dezent zum Online-Gehen auffordern.
        if premium and not self._grace_warned:
            remaining = keygen.grace_warning_days(
                keygen.default_cache_path(), datetime.now()
            )
            if remaining is not None:
                self._grace_warned = True
                QMessageBox.information(
                    self,
                    tr("license_grace_title", self.language),
                    tr("license_grace_msg", self.language, days=remaining),
                )

    def _set_keygen_premium(self, premium: bool) -> None:
        self._keygen_premium = premium

    def _premium_active(self, settings) -> bool:
        """Premium, wenn eigene Offline-Signatur ODER Keygen (gecacht) gültig ist."""
        offline = is_feature_enabled("rename", load_license(settings.license_key))
        return bool(offline or self._keygen_premium)

    def _rename_one_file(self, old_path: str, new_path: str) -> str | None:
        """Benennt eine Datei um; gibt None zurück oder die Fehlermeldung.

        Windows gibt ein gerade geschlossenes Datei-Handle (z. B. vom Player)
        nicht immer sofort frei. Deshalb ein paar kurze Wiederholungen, bevor
        endgültig ein Fehler gemeldet wird.
        """
        last_error: OSError | None = None
        for attempt in range(5):
            try:
                Path(old_path).rename(new_path)
                return None
            except OSError as error:
                last_error = error
                QApplication.processEvents()
                time.sleep(0.05 * (attempt + 1))
        return str(last_error)

    def rename_files(self) -> None:
        """Benennt die geladenen Dateien nach dem eingestellten Schema um.

        Vorschau (alt->neu) über den bestehenden ChangePreviewDialog, danach
        die eigentliche Umbenennung mit Kollisionsschutz aus plan_renames.
        Der Vorgang wird als rückgängig-fähiger History-Eintrag protokolliert;
        die Ansicht wird per scan_music neu vom Datenträger eingelesen.
        """
        settings = load_settings()
        premium = self._premium_active(settings)
        # In der zeitbasierten Testphase ist ebenfalls alles freigeschaltet.
        trial = usage_limits.trial_active(datetime.now())
        unlocked = premium or trial
        # Ohne Freischaltung sind FREE_RENAME_LIMIT Umbenennungen gratis; erst
        # danach (oder bei vorhandenem, aber unbestätigtem Schlüssel) wird
        # geblockt – dann kommt der freundliche Premium-Hinweis.
        if not unlocked and usage_limits.remaining_free_renames() <= 0:
            if settings.license_key.strip() and keygen.is_configured():
                title = tr("license_needs_online_title", self.language)
                message = tr("license_needs_online_msg", self.language)
                show_enter = False
            else:
                title = tr("premium_required_title", self.language)
                message = tr("free_limit_reached_msg", self.language)
                show_enter = True
            dialog = PremiumDialog(
                self,
                language=self.language,
                title=title,
                message=message,
                show_enter_license=show_enter,
            )
            if dialog.exec() == PremiumDialog.DialogCode.Accepted:
                self.open_settings()
                self.settings_workspace.focus_license_tab()
            return

        if not self.songs:
            QMessageBox.information(
                self,
                tr("rename_action", self.language),
                tr("rename_none", self.language),
            )
            return

        pattern = settings.rename_pattern
        plans = plan_renames(self.songs, pattern)
        applicable = [plan for plan in plans if plan.applies]
        skipped = [
            plan
            for plan in plans
            if not plan.applies and plan.reason in ("collision", "target_exists")
        ]

        if not applicable:
            QMessageBox.information(
                self,
                tr("rename_action", self.language),
                tr("rename_none", self.language),
            )
            return

        field = tr("rename_field", self.language)
        changes = [
            (plan.old_name, field, plan.old_name, plan.new_name)
            for plan in applicable
        ]
        accepted = (
            ChangePreviewDialog(
                changes,
                self,
                file_count=len(applicable),
                language=self.language,
            ).exec()
            == ChangePreviewDialog.DialogCode.Accepted
        )
        if not accepted:
            return

        # Falls der Player gerade eine der Dateien abspielt, hält Windows sie
        # gesperrt (WinError 32). Vor dem Umbenennen die Datei freigeben.
        applicable_keys = {
            str(Path(plan.old_path).resolve()).casefold() for plan in applicable
        }
        current = self.player_bar.engine.current_song
        if current and str(Path(current.path).resolve()).casefold() in applicable_keys:
            self.player_bar.engine.release_file()
            QApplication.processEvents()

        moves: list[tuple[str, str]] = []
        failed: list[str] = []
        for plan in applicable:
            error = self._rename_one_file(plan.old_path, plan.new_path)
            if error is None:
                moves.append((plan.old_path, plan.new_path))
            else:
                failed.append(f"{plan.old_name}: {error}")

        if moves:
            self.history.commit_rename("rename_history", moves)
            self.update_history_actions()
            # Gratis genutzte Umbenennungen zählen – nur wenn weder Lizenz noch
            # laufende Testphase (in der Testphase wird nichts vom Kontingent
            # abgezogen).
            if not unlocked:
                usage_limits.record_renames(len(moves))
            # Neu einlesen, damit Tabelle/Index die neuen Pfade übernehmen.
            self.scan_music()

        parts = [tr_plural("rename_done", len(moves), self.language)]
        if skipped:
            parts.append(
                tr_plural("rename_skipped", len(skipped), self.language)
            )
        # Hinweis auf Testphase bzw. verbleibendes Gratis-Kontingent.
        if trial and not premium:
            days = usage_limits.trial_days_remaining(datetime.now())
            parts.append(tr_plural("trial_days_left", days, self.language))
        elif not premium:
            remaining = usage_limits.remaining_free_renames()
            parts.append(
                tr_plural("free_renames_remaining", remaining, self.language)
            )
        self.statusBar().showMessage(" · ".join(parts), 8000)

        if failed:
            QMessageBox.warning(
                self,
                tr("rename_action", self.language),
                "\n".join(failed[:20]),
            )

    def open_library_audit(self):
        self.switch_workspace(3)

    def open_audio_analysis(self):
        self.switch_workspace(2)

    def open_settings(self):
        self.switch_workspace(4)

    def load_configured_sources(
        self,
    ) -> None:
        settings = load_settings()
        sources = tuple(
            source
            for source in settings.music_sources
            if source.enabled
        )
        self.library_index = update_source_availability(
            load_library_index(),
            sources,
        )
        self.media_library.set_library_index(
            self.library_index
        )
        self.dashboard_workspace.update_library(
            self.library_index,
            settings.music_sources,
        )

        if sources:
            self.folder = sources[0].path
            if len(sources) == 1:
                self.folder_label.setText(
                    tr(
                        "folder_label_single",
                        self.language,
                        path=sources[0].path,
                    )
                )
            else:
                names = ", ".join(
                    source.name
                    for source in sources
                )
                self.folder_label.setText(
                    tr(
                        "folder_label_multi",
                        self.language,
                        names=names,
                    )
                )

        if not settings.music_sources:
            self.switch_workspace(
                4
            )
            self.statusBar().showMessage(
                tr("add_source_first", self.language),
                8000,
            )
            return

        if not settings.load_sources_on_startup:
            return

        missing = [
            source
            for source in sources
            if not source.available
        ]

        if missing:
            lines = "\n".join(
                f"• {source.name}: {source.path}"
                for source in missing
            )
            QMessageBox.warning(
                self,
                tr("source_missing_title", self.language),
                tr("source_missing_msg", self.language, lines=lines),
            )

        if settings.scan_sources_on_startup:
            self.scan_configured_sources(
                sources
            )

    def scan_configured_sources(
        self,
        sources: tuple[MusicSource, ...] | None = None,
    ) -> None:
        settings = load_settings()

        if sources is None:
            sources = tuple(
                source
                for source in settings.music_sources
                if source.enabled
            )

        online_sources = tuple(
            source
            for source in sources
            if source.available
        )

        if not online_sources:
            return

        self.source_scan_worker = FunctionWorker(
            self._scan_sources_worker,
            online_sources,
        )
        self.source_scan_worker.signals.finished.connect(
            self._source_scan_finished
        )
        self.source_scan_worker.signals.failed.connect(
            self._source_scan_failed
        )
        QThreadPool.globalInstance().start(
            self.source_scan_worker
        )

    def _scan_sources_worker(
        self,
        sources: tuple[MusicSource, ...],
    ):
        summaries = []
        songs: list[Song] = []
        failures = []
        detected_files = 0

        for source in sources:
            result = scan_folder_detailed(
                source.path
            )
            source_songs = list(
                result.songs
            )
            summaries.append(
                index_songs(
                    source,
                    source_songs,
                )
            )
            songs.extend(
                source_songs
            )
            failures.extend(
                result.failures
            )
            detected_files += (
                result.detected_files
            )

        return {
            "sources": sources,
            "summaries": summaries,
            "songs": songs,
            "failures": failures,
            "detected_files": detected_files,
        }

    def _source_scan_finished(
        self,
        payload,
    ) -> None:
        settings = load_settings()

        if isinstance(
            payload,
            dict,
        ):
            summaries = list(
                payload.get(
                    "summaries",
                    [],
                )
            )
            songs = list(
                payload.get(
                    "songs",
                    [],
                )
            )
            sources = tuple(
                payload.get(
                    "sources",
                    (),
                )
            )
            failures = list(
                payload.get(
                    "failures",
                    [],
                )
            )
        else:
            summaries = list(
                payload
            )
            songs = []
            sources = tuple()
            failures = []

        self.library_index = merge_scan_results(
            self.library_index,
            summaries,
            settings.music_sources,
        )
        save_library_index(
            self.library_index
        )
        self.media_library.set_library_index(
            self.library_index
        )
        self.dashboard_workspace.update_library(
            self.library_index,
            settings.music_sources,
        )

        if sources:
            self.folder = sources[0].path
            if len(sources) == 1:
                self.folder_label.setText(
                    tr(
                        "folder_label_single",
                        self.language,
                        path=sources[0].path,
                    )
                )
            else:
                names = ", ".join(
                    source.name
                    for source in sources
                )
                self.folder_label.setText(
                    tr(
                        "folder_label_multi",
                        self.language,
                        names=names,
                    )
                )

        if songs:
            self._apply_songs_to_tagger(
                songs
            )

        self.source_scan_worker = None
        self.statusBar().showMessage(
            tr(
                "library_updated",
                self.language,
                tracks=len(songs),
                albums=len(self.library_index),
            ),
            6000,
        )

        if failures:
            QMessageBox.warning(
                self,
                tr("skipped_files_title", self.language),
                tr("skipped_files_log_msg", self.language, count=len(failures)),
            )

    def _source_scan_failed(
        self,
        message: str,
    ) -> None:
        self.source_scan_worker = None
        QMessageBox.warning(
            self,
            tr("sources_update_failed_title", self.language),
            message,
        )

    def rescan_library(
        self,
    ) -> None:
        if not self.confirm_pending_changes():
            return

        settings = load_settings()
        sources = tuple(
            source
            for source in settings.music_sources
            if source.enabled
            and source.available
        )

        if sources:
            self.scan_configured_sources(
                sources
            )
            return

        self.scan_music()

    def select_folder(self):
        if not self.confirm_pending_changes():
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            tr("music_folder", self.language),
            self.folder or "",
        )

        if folder:
            self.folder = folder
            self.folder_label.setText(
                tr(
                    "folder_label_single",
                    self.language,
                    path=folder,
                )
            )
            self.scan_music()

    def scan_music(self):
        if not self.confirm_pending_changes():
            return

        if not self.folder or not Path(self.folder).is_dir():
            QMessageBox.warning(
                self,
                tr("folder_not_found_title", self.language),
                tr("folder_not_found_msg", self.language, folder=self.folder or ""),
            )
            return

        scan_result = scan_folder_detailed(
            self.folder
        )
        songs = list(
            scan_result.songs
        )

        if scan_result.failures:
            details = "\n\n".join(
                f"{failure.path}\n{failure.error}"
                for failure
                in scan_result.failures[:20]
            )
            if len(scan_result.failures) > 20:
                details += "\n\n" + tr(
                    "and_more_files",
                    self.language,
                    count=len(scan_result.failures) - 20,
                )
            QMessageBox.warning(
                self,
                tr("skipped_files_title", self.language),
                tr(
                    "skipped_files_scan_msg",
                    self.language,
                    detected=scan_result.detected_files,
                    successful=scan_result.successful_files,
                    skipped=len(scan_result.failures),
                    details=details,
                ),
            )
        elif scan_result.detected_files == 0:
            QMessageBox.information(
                self,
                tr("no_audio_title", self.language),
                tr("no_audio_msg", self.language),
            )

        self._apply_songs_to_tagger(
            songs
        )

        settings = load_settings()
        matching_source = next(
            (
                source
                for source in settings.music_sources
                if (
                    Path(self.folder).resolve()
                    == Path(source.path).resolve()
                    or Path(source.path).resolve()
                    in Path(self.folder).resolve().parents
                )
            ),
            None,
        )

        if matching_source is not None:
            summary = index_songs(
                matching_source,
                songs,
            )
            self.library_index = merge_scan_results(
                self.library_index,
                [summary],
                settings.music_sources,
            )
            save_library_index(
                self.library_index
            )
            self.media_library.set_library_index(
                self.library_index
            )
            self.dashboard_workspace.update_library(
                self.library_index,
                settings.music_sources,
            )

    def _on_duplicates_deleted(self, deleted_paths: list) -> None:
        """Entfernte Dubletten aus der Tagger-Liste nehmen und Ansicht neu füllen."""
        removed = set(deleted_paths)
        if not removed:
            return
        remaining = [song for song in self.songs if song.path not in removed]
        self._apply_songs_to_tagger(remaining)

    def _apply_songs_to_tagger(
        self,
        songs: list[Song],
    ) -> None:
        self.songs = list(
            songs
        )
        self.media_library.set_local_songs(
            self.songs
        )

        self.current_row = -1
        self.active_rows = []
        self.previous_rows = []
        self.clear_editor()

        self.table.blockSignals(
            True
        )
        self.table.clearContents()
        self.table.setRowCount(
            len(
                self.songs
            )
        )

        for row, song in enumerate(
            self.songs
        ):
            self.update_table_row(
                row,
                song,
            )

        self.table.blockSignals(
            False
        )
        self.update_optional_columns()
        if hasattr(self, "filter_genre"):
            self._populate_filter_combos()
            self._apply_song_filter()

        enabled = bool(
            self.songs
        )
        self.proposal_button.setEnabled(
            enabled
        )
        self.identify_button.setEnabled(
            enabled
        )
        self.batch_button.setEnabled(
            enabled
        )
        self.auto_tag_button.setEnabled(
            enabled
        )
        self.convert_button.setEnabled(
            enabled
        )
        self.cover_button.setEnabled(
            enabled
        )
        self._update_lyrics_button()
        self.direct_album_button.setEnabled(
            enabled
        )
        self._update_release_text_button()
        self._update_more_artist_button()

        if not enabled:
            return

        self.table.selectRow(
            0
        )
        self.table.setCurrentCell(
            0,
            0,
        )
        self.handle_selection_changed()
        self._update_release_text_button()
        self._update_more_artist_button()
        self.table.setFocus()

    def selected_rows(self) -> list[int]:
        selection_model = self.table.selectionModel()

        if selection_model is None:
            return []

        return sorted(
            {
                index.row()
                for index in selection_model.selectedRows()
            }
        )

    def handle_selection_changed(self):
        rows = self.selected_rows()
        self._update_release_text_button()
        self._update_more_artist_button()
        self._update_lyrics_button()

        if rows == self.active_rows:
            return

        if self.has_unsaved_changes:
            if not self.confirm_pending_changes():
                self.restore_rows(self.active_rows)
                return

        self.previous_rows = self.active_rows.copy()
        self.active_rows = rows

        if not rows:
            self.current_row = -1
            self.clear_editor()
            self._update_release_text_button()
            self._update_lyrics_button()
            return

        if len(rows) == 1:
            self.display_single_song(rows[0])
        else:
            self.display_multiple_songs(rows)

    def display_single_song(self, row: int):
        song = self.songs[row]
        self.current_row = row
        self.loading_editor = True
        self.batch_touched_fields.clear()
        self.batch_original_values = {}

        values = song_values(song)

        for name, field in self.editor_fields.items():
            field.setPlaceholderText("")
            field.setText(values.get(name, ""))

        self.original_values = values.copy()
        self.loading_editor = False
        self.update_dirty_state()

        self.selection_label.setText(
            tr(
                "selection_one_msg",
                self.language,
                album=song.album or tr("no_album", self.language),
            )
        )
        self.show_cover(load_cover(song.path))

        self.proposal_button.setEnabled(True)

    def display_multiple_songs(self, rows: list[int]):
        selected_songs = [self.songs[row] for row in rows]
        self.current_row = rows[-1]
        self.loading_editor = True
        self.original_values = {}
        self.batch_touched_fields.clear()
        self.batch_original_values = {}

        album_keys = {
            ((song.album_artist or song.artist).casefold(), song.album.casefold())
            for song in selected_songs
        }
        same_album = len(album_keys) == 1

        for name, field in self.editor_fields.items():
            values = [str(getattr(song, name, "") or "") for song in selected_songs]
            common_value = values[0] if values and all(value == values[0] for value in values) else None

            # Bei einer vollständigen Albumauswahl ist die Gesamtzahl der Tracks
            # die Anzahl der ausgewählten Titel, auch wenn ältere Tags abweichen.
            if name == "total_tracks" and same_album and len(rows) == len(self.songs):
                common_value = str(len(rows))

            self.batch_original_values[name] = common_value
            if common_value is None:
                field.clear(); field.setPlaceholderText(MIXED_VALUE_PLACEHOLDER)
            else:
                field.setPlaceholderText(""); field.setText(common_value)
            field.setStyleSheet(INPUT_NORMAL)

        self.loading_editor = False
        self.has_unsaved_changes = False
        album_count = len(album_keys)
        album_word = tr_plural("album_count", album_count, self.language)
        self.selection_label.setText(
            tr(
                "selection_multi_msg",
                self.language,
                tracks=len(rows),
                albums=album_count,
                album_word=album_word,
            )
        )
        self.show_multiple_selection_cover(rows)
        self.proposal_button.setEnabled(False)
        self.update_save_button()

    def show_multiple_selection_cover(
        self,
        rows: list[int],
    ):
        """
        Zeigt bei einer Mehrfachauswahl das gemeinsame Cover.

        Nur wenn sich Bilddaten oder technische Eigenschaften unterscheiden,
        wird „Unterschiedliche Cover“ angezeigt. Eine Mischung aus Dateien
        mit und ohne Cover gilt ebenfalls als Unterschied.
        """
        cover_infos = [
            load_cover_info(self.songs[row].path)
            for row in rows
        ]

        if not covers_are_identical(cover_infos):
            self.current_cover = None
            self.cover_label.clear()
            self.cover_label.setText(
                "Unterschiedliche Cover"
            )
            return

        common_cover = cover_infos[0] if cover_infos else None

        if common_cover is None:
            self.current_cover = None
            self.cover_label.clear()
            self.cover_label.setText(
                "Kein Cover vorhanden"
            )
            return

        self.show_cover(common_cover.data)

    def manage_cover(self):
        rows = self.selected_rows()

        if not rows:
            return

        songs = [
            self.songs[row]
            for row in rows
        ]
        album_keys = {
            (
                (
                    song.album_artist
                    or song.artist
                ).casefold(),
                song.album.casefold(),
            )
            for song in songs
        }

        settings = load_settings()
        manager = CoverManager(settings)

        if len(album_keys) != 1:
            plans = build_album_cover_plans(
                manager,
                songs,
            )
            dialog = BatchCoverDialog(
                manager,
                plans,
                self,
                language=self.language,
            )
            dialog.exec()
            self.refresh_active_editor()
            return

        cover_logger = get_diagnostic_logger(
            "cover"
        )
        cover_logger.info(
            "COVERDIALOG ÖFFNEN | Titel=%d | Album=%r | Datei=%s",
            len(songs),
            songs[0].album,
            songs[0].path,
        )
        dialog = CoverSelectionDialog(
            manager,
            songs[0],
            self,
            language=self.language,
        )

        if (
            dialog.exec()
            != dialog.DialogCode.Accepted
            or dialog.selected_candidate
            is None
        ):
            return

        entry = self.history.begin(
            "hist_cover_changed",
            [
                song.path
                for song in songs
            ],
        )
        QApplication.setOverrideCursor(
            Qt.CursorShape.WaitCursor
        )

        try:
            result = manager.apply(
                dialog.selected_candidate,
                songs,
            )
            self.history.commit(
                entry
            )
            self.update_history_actions()
        except Exception as error:
            self.history.rollback_pending(
                entry
            )
            QMessageBox.critical(
                self,
                tr("cover_failed_title", self.language),
                str(error),
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.refresh_active_editor()

        QMessageBox.information(
            self,
            tr("cover_saved_title", self.language),
            tr(
                "cover_saved_msg",
                self.language,
                master=result.master_path,
                folder_cover=result.folder_cover_path,
                embedded=result.embedded_files,
            ),
        )

    def load_direct_album(self):
        rows = self.selected_rows()

        if not rows:
            return

        songs = [
            self.songs[row]
            for row in rows
        ]
        settings = load_settings()
        dialog = DirectAlbumDialog(
            songs,
            settings.apple_country,
            self,
            language=self.language,
        )

        if (
            dialog.exec()
            != dialog.DialogCode.Accepted
            or dialog.result is None
        ):
            return

        proposals: list[
            BatchSongProposal
        ] = []

        for local_index, track in (
            dialog.matches.items()
        ):
            song_row = rows[local_index]
            candidate = track.as_candidate(
                dialog.result.provider
            )

            proposals.append(
                BatchSongProposal(
                    song_row=song_row,
                    song=self.songs[song_row],
                    candidates=[candidate],
                    warnings=[],
                )
            )

        if not proposals:
            return

        comparison = BatchComparisonDialog(
            proposals,
            primary_source=(
                dialog.result.provider
            ),
            feature_handling=(
                settings.feature_handling
            ),
            parent=self,
            language=self.language,
        )

        if (
            comparison.exec()
            != comparison.DialogCode.Accepted
        ):
            return

        update_items = [
            (
                song_row,
                replace(
                    self.songs[
                        song_row
                    ],
                    **updates,
                ),
            )
            for song_row, updates
            in comparison.selected_updates.items()
        ]
        saved, failed = (
            self._write_song_updates(
                "hist_direct_album",
                update_items,
            )
        )

        self.update_optional_columns()
        self.refresh_active_editor()

        message = tr(
            "direct_album_done_msg",
            self.language,
            count=saved,
        )

        if failed:
            message += tr(
                "errors_block",
                self.language,
                errors="\n".join(failed),
            )

        QMessageBox.information(
            self,
            tr("direct_album_done_title", self.language),
            message,
        )

    def mark_field_edited(self, field_name: str):
        if self.loading_editor:
            return

        if len(self.active_rows) > 1:
            self.batch_touched_fields.add(field_name)

    def create_single_proposal(self):
        if len(self.active_rows) != 1:
            return

        if self.has_unsaved_changes:
            if not self.confirm_pending_changes():
                return

        row = self.active_rows[0]

        QApplication.setOverrideCursor(
            Qt.CursorShape.WaitCursor
        )

        try:
            result = build_proposal(self.songs[row])
        finally:
            QApplication.restoreOverrideCursor()

        settings = load_settings()

        dialog = ComparisonDialog(
            self.songs[row],
            result.candidates,
            primary_source=settings.selected_provider,
            feature_handling=settings.feature_handling,
            warnings=result.warnings,
            parent=self,
            language=self.language,
        )

        if (
            dialog.exec()
            != dialog.DialogCode.Accepted
            or not dialog.selected_fields
        ):
            return

        self.loading_editor = True

        for name, value in (
            dialog.selected_values.items()
        ):
            self.editor_fields[name].setText(
                value
            )

        self.loading_editor = False
        self.update_dirty_state()

    def identify_by_sound(self):
        """Identifiziert den ausgewählten Titel per akustischem Fingerabdruck."""
        if len(self.active_rows) != 1:
            QMessageBox.information(
                self,
                tr("identify_by_sound", self.language),
                tr("identify_select_one_msg", self.language),
            )
            return

        if self.has_unsaved_changes:
            if not self.confirm_pending_changes():
                return

        row = self.active_rows[0]
        song = self.songs[row]

        if not Path(song.path).is_file():
            QMessageBox.warning(
                self,
                tr("identify_by_sound", self.language),
                tr("identify_file_missing_msg", self.language),
            )
            return

        settings = load_settings()
        api_key = fingerprint.resolve_api_key(settings.acoustid_api_key)

        if not api_key:
            QMessageBox.information(
                self,
                tr("identify_by_sound", self.language),
                tr("identify_no_key_msg", self.language),
            )
            return

        candidates: list = []
        error_message = ""

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            matches = fingerprint.identify_recording(
                song.path,
                api_key=api_key,
                fpcalc_path=settings.fpcalc_path,
            )
            seen: set[str] = set()

            for match in matches[:3]:
                if match.recording_id in seen:
                    continue
                seen.add(match.recording_id)

                candidate = lookup_recording_by_id(match.recording_id)

                if candidate is not None:
                    candidates.append(
                        replace(
                            candidate,
                            confidence=int(round(match.score * 100)),
                        )
                    )
        except fingerprint.FingerprintError as error:
            error_message = str(error)
        except MusicBrainzProviderError as error:
            error_message = str(error)
        finally:
            QApplication.restoreOverrideCursor()

        if error_message:
            QMessageBox.warning(
                self,
                tr("identify_by_sound", self.language),
                error_message,
            )
            return

        if not candidates:
            QMessageBox.information(
                self,
                tr("identify_by_sound", self.language),
                tr("identify_no_match_msg", self.language),
            )
            return

        dialog = ComparisonDialog(
            song,
            candidates,
            primary_source="musicbrainz",
            feature_handling=settings.feature_handling,
            parent=self,
            language=self.language,
        )

        if (
            dialog.exec() != dialog.DialogCode.Accepted
            or not dialog.selected_fields
        ):
            return

        self.loading_editor = True

        for name, value in dialog.selected_values.items():
            self.editor_fields[name].setText(value)

        self.loading_editor = False
        self.update_dirty_state()

    def create_batch_proposals(self):
        if self.has_unsaved_changes:
            if not self.confirm_pending_changes():
                return

        rows = self.selected_rows()

        if not rows:
            rows = list(range(len(self.songs)))

        progress = QProgressDialog(
            tr("querying_providers", self.language),
            tr("cancel", self.language),
            0,
            len(rows),
            self,
        )
        progress.setWindowModality(
            Qt.WindowModality.WindowModal
        )

        selected_songs = [
            self.songs[row]
            for row in rows
        ]

        def update_progress(
            position: int,
            total: int,
            title: str,
        ):
            progress.setMaximum(
                max(1, total)
            )
            progress.setValue(position)
            progress.setLabelText(
                f"{min(position + 1, total)}/{total}: "
                f"{title}"
            )
            QApplication.processEvents()

        results = build_batch_proposals(
            selected_songs,
            progress_callback=(
                update_progress
            ),
            cancel_callback=(
                progress.wasCanceled
            ),
        )

        proposals: list[
            BatchSongProposal
        ] = []

        for row, result in zip(
            rows,
            results,
        ):
            proposals.append(
                BatchSongProposal(
                    song_row=row,
                    song=self.songs[row],
                    candidates=(
                        result.candidates
                    ),
                    warnings=result.warnings,
                )
            )

        progress.setValue(len(rows))

        if not proposals:
            return

        settings = load_settings()

        dialog = BatchComparisonDialog(
            proposals,
            primary_source=settings.selected_provider,
            feature_handling=settings.feature_handling,
            parent=self,
            language=self.language,
        )

        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        update_items = [
            (
                song_row,
                replace(
                    self.songs[
                        song_row
                    ],
                    **updates,
                ),
            )
            for song_row, updates
            in dialog.selected_updates.items()
        ]
        saved, failed = (
            self._write_song_updates(
                "hist_batch_suggestions",
                update_items,
            )
        )

        self.update_optional_columns()

        message = tr("batch_saved_msg", self.language, count=saved)

        if failed:
            message += tr(
                "errors_block",
                self.language,
                errors="\n".join(failed),
            )

        QMessageBox.information(
            self,
            tr("batch_done_title", self.language),
            message,
        )

        self.refresh_active_editor()

    def _build_filter_bar(self):
        """Filterleiste über der Tabelle: freie Suche + Genre + Künstler."""
        row = QHBoxLayout()
        self.filter_search = QLineEdit()
        self.filter_search.setClearButtonEnabled(True)
        self.filter_search.setPlaceholderText(tr("filter_search_placeholder", self.language))
        self.filter_search.textChanged.connect(self._apply_song_filter)

        self.filter_genre = QComboBox()
        self.filter_genre.currentIndexChanged.connect(self._apply_song_filter)
        self.filter_artist = QComboBox()
        self.filter_artist.currentIndexChanged.connect(self._apply_song_filter)

        self.filter_count_label = QLabel("")
        self.filter_count_label.setStyleSheet("color: palette(mid);")

        row.addWidget(self.filter_search, 3)
        row.addWidget(QLabel(tr("filter_genre_label", self.language)))
        row.addWidget(self.filter_genre, 2)
        row.addWidget(QLabel(tr("filter_artist_label", self.language)))
        row.addWidget(self.filter_artist, 2)
        row.addWidget(self.filter_count_label)
        return row

    def _populate_filter_combos(self):
        """Genre-/Künstler-Auswahl aus den geladenen Titeln neu befüllen."""
        from ..services.song_filter import distinct_values

        for combo, field, all_key in (
            (self.filter_genre, "genre", "filter_all_genres"),
            (self.filter_artist, "artist", "filter_all_artists"),
        ):
            previous = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(tr(all_key, self.language), "")
            for value in distinct_values(self.songs, field):
                combo.addItem(value, value)
            index = combo.findData(previous) if previous else 0
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def _apply_song_filter(self, *_args):
        """Blendet Zeilen aus, die nicht zu Suche/Genre/Künstler passen."""
        from ..services.song_filter import matches

        text = self.filter_search.text() if hasattr(self, "filter_search") else ""
        genre = self.filter_genre.currentData() or ""
        artist = self.filter_artist.currentData() or ""
        visible = 0
        for row, song in enumerate(self.songs):
            ok = matches(song, text=text, genre=genre, artist=artist)
            self.table.setRowHidden(row, not ok)
            if ok:
                visible += 1
        if text or genre or artist:
            self.filter_count_label.setText(
                tr("filter_count", self.language, shown=visible, total=len(self.songs))
            )
        else:
            self.filter_count_label.setText("")

    def _flush_listening(self) -> None:
        """Bisher gespielte Zeit des laufenden Titels in die Statistik buchen."""
        import time

        if self._listen_started is not None and self._listen_song is not None:
            elapsed = time.monotonic() - self._listen_started
            self.listening_stats.record(self._listen_song, elapsed)
        self._listen_started = None

    def _on_playback_for_stats(self, playing: bool) -> None:
        import time

        self._listen_playing = playing
        if playing:
            self._listen_song = self.player_bar.engine.current_song
            self._listen_started = time.monotonic()
        else:
            self._flush_listening()

    def _on_song_for_stats(self, song) -> None:
        import time

        self._flush_listening()  # vorherigen Titel abrechnen
        self._listen_song = song
        if self._listen_playing and song is not None:
            self._listen_started = time.monotonic()

    def _show_listening_stats(self) -> None:
        from .listening_stats_dialog import ListeningStatsDialog

        ListeningStatsDialog(
            self.listening_stats, self, language=self.language
        ).exec()

    def _detach_now_playing(self):
        """Öffnet die Wiedergabe-Ansicht als separates, schwebendes Fenster."""
        existing = getattr(self, "_now_playing_window", None)
        if existing is not None:
            existing.raise_()
            existing.activateWindow()
            return
        window = QWidget()
        window.setWindowTitle(tr("playback", self.language))
        window.resize(420, 640)
        inner = QVBoxLayout(window)
        inner.setContentsMargins(0, 0, 0, 0)
        detached_view = NowPlayingWidget(
            self.player_bar.engine,
            window,
            language=self.language,
            allow_detach=False,
            favorites=self.favorites,
        )
        detached_view.stats_requested.connect(self._show_listening_stats)
        inner.addWidget(detached_view)

        def _clear(_event=None):
            self._now_playing_window = None

        window.closeEvent = lambda event: (_clear(), event.accept())
        self._now_playing_window = window
        window.show()

    def convert_selected(self):
        """Öffnet den Konvertierungsdialog für die ausgewählten (oder alle) Titel."""
        rows = self.selected_rows() or list(range(len(self.songs)))
        songs = [self.songs[row] for row in rows if 0 <= row < len(self.songs)]
        if not songs:
            return
        ConversionDialog(songs, self, language=self.language).exec()

    def auto_tag_selected(self):
        """Batch-Auto-Tagging: hohe Konfidenz automatisch, Rest zur Prüfung."""
        if self.has_unsaved_changes and not self.confirm_pending_changes():
            return

        rows = self.selected_rows() or list(range(len(self.songs)))
        if not rows:
            return

        threshold, ok = QInputDialog.getInt(
            self,
            tr("auto_tag", self.language),
            tr("auto_tag_threshold_prompt", self.language),
            DEFAULT_THRESHOLD,
            50,
            100,
            5,
        )
        if not ok:
            return

        selected_songs = [self.songs[row] for row in rows]

        progress = QProgressDialog(
            tr("querying_providers", self.language),
            tr("cancel", self.language),
            0,
            len(rows),
            self,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        def update_progress(position, total, title):
            progress.setMaximum(max(1, total))
            progress.setValue(position)
            progress.setLabelText(f"{min(position + 1, total)}/{total}: {title}")
            QApplication.processEvents()

        results = build_batch_proposals(
            selected_songs,
            progress_callback=update_progress,
            cancel_callback=progress.wasCanceled,
        )
        progress.setValue(len(rows))

        settings = load_settings()
        decisions = run_auto_tag(
            selected_songs,
            results,
            primary_source=settings.selected_provider,
            threshold=threshold,
        )

        # Sichere Treffer automatisch übernehmen (mit Verlauf/Undo).
        update_items = [
            (rows[index], replace(self.songs[rows[index]], **decision.updates))
            for index, decision in enumerate(decisions)
            if decision.applied
        ]
        saved, failed = (
            self._write_song_updates("hist_auto_tag", update_items)
            if update_items
            else (0, [])
        )
        self.update_optional_columns()

        _applied, _review, no_match = summarize(decisions)
        review_indices = [
            index
            for index, decision in enumerate(decisions)
            if decision.reason == REASON_LOW_CONFIDENCE
        ]

        message = tr(
            "auto_tag_summary",
            self.language,
            applied=saved,
            review=len(review_indices),
            no_match=no_match,
        )
        if failed:
            message += tr(
                "errors_block", self.language, errors="\n".join(failed)
            )

        self.refresh_active_editor()

        if review_indices:
            answer = QMessageBox.question(
                self,
                tr("auto_tag", self.language),
                message + "\n\n" + tr("auto_tag_open_review", self.language),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._open_batch_review(
                    [rows[index] for index in review_indices],
                    [results[index] for index in review_indices],
                )
        else:
            QMessageBox.information(
                self, tr("auto_tag", self.language), message
            )

    def _open_batch_review(self, rows, results):
        """Öffnet den bestehenden Vergleichsdialog für die unsicheren Treffer."""
        proposals = [
            BatchSongProposal(
                song_row=row,
                song=self.songs[row],
                candidates=result.candidates,
                warnings=result.warnings,
            )
            for row, result in zip(rows, results)
        ]
        if not proposals:
            return
        settings = load_settings()
        dialog = BatchComparisonDialog(
            proposals,
            primary_source=settings.selected_provider,
            feature_handling=settings.feature_handling,
            parent=self,
            language=self.language,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        update_items = [
            (song_row, replace(self.songs[song_row], **updates))
            for song_row, updates in dialog.selected_updates.items()
        ]
        saved, failed = self._write_song_updates(
            "hist_batch_suggestions", update_items
        )
        self.update_optional_columns()
        message = tr("batch_saved_msg", self.language, count=saved)
        if failed:
            message += tr("errors_block", self.language, errors="\n".join(failed))
        QMessageBox.information(
            self, tr("batch_done_title", self.language), message
        )
        self.refresh_active_editor()

    def update_dirty_state(self):
        if self.loading_editor:
            return

        if len(self.active_rows) > 1:
            self.has_unsaved_changes = bool(
                self.batch_touched_fields
            )

            for name, field in self.editor_fields.items():
                field.setStyleSheet(
                    INPUT_CHANGED
                    if name in self.batch_touched_fields
                    else INPUT_NORMAL
                )
        elif len(self.active_rows) == 1:
            current = self.get_editor_values()

            for name, field in self.editor_fields.items():
                changed = (
                    current.get(name, "")
                    != self.original_values.get(name, "")
                )
                field.setStyleSheet(
                    INPUT_CHANGED
                    if changed
                    else INPUT_NORMAL
                )

            self.has_unsaved_changes = (
                bool(self.original_values)
                and current != self.original_values
            )
        else:
            self.has_unsaved_changes = False

        self.update_save_button()

    def update_save_button(self):
        count = len(self.active_rows)

        self.save_button.setEnabled(
            self.has_unsaved_changes
        )

        if count > 1:
            suffix = " *" if self.has_unsaved_changes else ""
            self.save_button.setText(
                tr("apply_to_tracks", self.language, count=count)
                + suffix
            )
        else:
            self.save_button.setText(
                BUTTON_CHANGED
                if self.has_unsaved_changes
                else BUTTON_NORMAL
            )

    def save_song(self):
        if len(self.active_rows) > 1:
            self.save_batch_edits()
        elif len(self.active_rows) == 1:
            self.save_single_edit()

    def save_single_edit(self):
        row = self.active_rows[0]
        values = self.get_editor_values()
        updated = replace(
            self.songs[row],
            **values,
        )

        saved, failed = (
            self._write_song_updates(
                "hist_single_edit",
                [
                    (
                        row,
                        updated,
                    )
                ],
            )
        )

        if not saved:
            if failed:
                QMessageBox.critical(
                    self,
                    tr("save_failed_title", self.language),
                    "\n".join(
                        failed
                    ),
                )
            return

        self.update_optional_columns()

        self.original_values = values.copy()
        self.update_dirty_state()

        QMessageBox.information(
            self,
            tr("saved_title", self.language),
            tr("saved_msg", self.language),
        )

    def save_batch_edits(self):
        rows = self.active_rows.copy()
        touched_fields = set(
            self.batch_touched_fields
        )

        if not rows or not touched_fields:
            return

        answer = QMessageBox.question(
            self,
            tr("batch_confirm_title", self.language),
            tr(
                "batch_confirm_msg",
                self.language,
                count=len(rows),
            ),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if answer != QMessageBox.StandardButton.Save:
            return

        edited_values = self.get_editor_values()
        update_items = []

        for row in rows:
            updates = {
                name: edited_values[
                    name
                ]
                for name in touched_fields
            }
            update_items.append(
                (
                    row,
                    replace(
                        self.songs[row],
                        **updates,
                    ),
                )
            )

        saved_count, failed = (
            self._write_song_updates(
                "hist_batch_edit",
                update_items,
            )
        )
        saved_rows = (
            rows[:saved_count]
            if saved_count
            else []
        )

        self.update_optional_columns()

        if saved_rows:
            self.display_multiple_songs(rows)

        message = tr(
            "batch_edit_done_msg",
            self.language,
            saved=len(saved_rows),
            total=len(rows),
        )

        if failed:
            message += tr(
                "errors_block",
                self.language,
                errors="\n".join(failed),
            )

        QMessageBox.information(
            self,
            tr("batch_edit_done_title", self.language),
            message,
        )

    def confirm_pending_changes(self) -> bool:
        if not self.has_unsaved_changes:
            return True

        count = len(self.active_rows)

        if count > 1:
            message = tr(
                "unsaved_multi_msg",
                self.language,
                count=count,
            )
        else:
            message = tr("unsaved_single_msg", self.language)

        answer = QMessageBox.warning(
            self,
            tr("unsaved_title", self.language),
            message,
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if answer == QMessageBox.StandardButton.Save:
            self.save_song()
            return not self.has_unsaved_changes

        return (
            answer
            == QMessageBox.StandardButton.Discard
        )

    def restore_rows(self, rows: list[int]):
        self.table.blockSignals(True)
        self.table.clearSelection()

        for row in rows:
            self.table.selectRow(row)

        if rows:
            self.table.setCurrentCell(
                rows[-1],
                0,
            )

        self.table.blockSignals(False)

    def get_editor_values(self) -> dict[str, str]:
        return {
            name: field.text()
            for name, field in self.editor_fields.items()
        }

    @staticmethod
    def _format_number_pair(
        current: str,
        total: str = "",
    ) -> str:
        def padded(
            value: str,
        ) -> str:
            text = str(
                value or ""
            ).strip()

            try:
                return f"{int(text):02d}"
            except ValueError:
                return text

        current_text = padded(
            current
        )
        total_text = padded(
            total
        )

        if total_text:
            return (
                f"{current_text}/{total_text}"
            )

        return current_text

    def update_table_row(
        self,
        row: int,
        song: Song,
    ):
        track = self._format_number_pair(
            song.track,
            song.total_tracks,
        )
        disc = self._format_number_pair(
            song.disc,
            song.total_discs,
        )

        values = [
            track,
            song.title,
            song.artist,
            song.album,
            disc,
            song.year,
            song.isrc,
            song.label,
            song.copyright,
            song.composer,
            song.comment,
            song.path,
        ]

        for column, value in enumerate(values):
            self.table.setItem(
                row,
                column,
                QTableWidgetItem(value),
            )

    def update_optional_columns(self):
        for field_name in OPTIONAL_FIELDS:
            column = self.table_fields.index(
                field_name
            )
            has_value = any(
                getattr(song, field_name).strip()
                for song in self.songs
            )
            self.table.setColumnHidden(
                column,
                not has_value,
            )

    def show_cover(self, data: bytes | None):
        if not data:
            self.current_cover = None
            self.cover_label.clear()
            self.cover_label.setText(
                "Kein Cover vorhanden"
            )
            return

        pixmap = QPixmap()

        if not pixmap.loadFromData(data):
            return

        self.current_cover = pixmap
        self.cover_label.setPixmap(
            pixmap.scaled(
                self.cover_label.contentsRect().size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def refresh_active_editor(self):
        rows = self.active_rows.copy()

        if not rows:
            self.clear_editor()
        elif len(rows) == 1:
            self.display_single_song(rows[0])
        else:
            self.display_multiple_songs(rows)

    def clear_editor(self):
        self.loading_editor = True

        for field in self.editor_fields.values():
            field.clear()
            field.setPlaceholderText("")
            field.setStyleSheet(INPUT_NORMAL)

        self.loading_editor = False
        self.original_values = {}
        self.batch_original_values = {}
        self.batch_touched_fields.clear()
        self.has_unsaved_changes = False
        self.current_row = -1

        self.selection_label.setText(
            tr("no_track_selected", self.language)
        )
        self.save_button.setEnabled(False)
        self.save_button.setText(BUTTON_NORMAL)

        self.cover_label.clear()
        self.cover_label.setText(
            "Kein Cover vorhanden"
        )

    def _show_player_status(self, message: str, timeout: int) -> None:
        """Zeigt eine transiente Player-Meldung in der Statusleiste an."""
        self.statusBar().showMessage(message, timeout)

    def closeEvent(self, event: QCloseEvent):
        if self.confirm_pending_changes():
            self._flush_listening()  # laufende Hörzeit noch verbuchen
            self.player_bar.save_queue()
            self.windows_system_media.stop()
            self.windows_media_keys.stop()
            self.player_bar.engine.stop()
            event.accept()
        else:
            event.ignore()
