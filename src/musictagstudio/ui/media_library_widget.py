from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import html
import re
import urllib.error
import urllib.request
import webbrowser

from PySide6.QtCore import (
    QObject,
    QSettings,
    QSize,
    QRunnable,
    QThreadPool,
    Signal,
    Slot,
    Qt,
)
from PySide6.QtGui import (
    QIcon,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
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
    DiscogsCatalogSnapshot,
    Edition,
    ReleaseGroup,
    Track,
    fetch_artist_release_groups,
    fetch_release_group_editions,
    fetch_release_tracklist,
    ArtistRelationsResponse,
    ArtistSearchResponse,
    ReleaseGroupResponse,
    default_controller,
    fetch_discogs_artist_releases,
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
from ..services.cover import load_cover
from ..providers.apple_music import (
    AppleMusicProviderError,
    search_album as search_apple_album,
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


class MediaLibraryWidget(QWidget):
    open_local_album = Signal(str)

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
        self.editions: list[
            Edition
        ] = []
        self.current_group: (
            ReleaseGroup
            | None
        ) = None
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
        self.release_view_mode = str(self.ui_settings.value("media_library/view_mode", "discography"))
        self.cover_size_name = str(self.ui_settings.value("media_library/cover_size", "medium"))
        self._view_syncing = False
        self.language = load_settings().language
        self.catalog_controller = default_controller
        self.search_debug_lines: list[str] = []
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
        self.search_edit.setPlaceholderText(
            tr("search_artist_placeholder", self.language)
        )
        self.search_edit.returnPressed.connect(
            self.search
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
        self.group_tree.setHeaderLabels(["Veröffentlichung", "Jahr", "Kategorie", "Quelle", "Lokal"])
        self.group_tree.setIconSize(QSize(18,18)); self.group_tree.setIndentation(22); self.group_tree.setColumnCount(5)
        self.group_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.group_tree.currentItemChanged.connect(self._group_selected)
        self.release_view_stack.addWidget(self.group_tree)
        self.release_table = QTableWidget(0,7)
        self.release_table.setHorizontalHeaderLabels(["Titel","Künstler","Jahr","Kategorie","Quelle","Label / Format","Lokal"])
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
        detail_layout = QVBoxLayout(
            detail_panel
        )
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

        self.group_meta = QLabel("")
        self.group_meta.setWordWrap(
            True
        )
        detail_text.addWidget(
            self.group_meta
        )
        detail_text.addStretch()
        detail_header.addLayout(
            detail_text,
            stretch=1,
        )
        detail_layout.addLayout(
            detail_header
        )

        service_row = QHBoxLayout()
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
        service_row.addWidget(
            self.streaming_button
        )
        service_row.addWidget(
            self.quality_button
        )
        service_row.addWidget(
            self.apple_button
        )
        detail_layout.addLayout(
            service_row
        )

        self.streaming_status = QLabel(
            "Streaming und Qualität wurden nicht abgefragt."
        )
        self.streaming_status.setWordWrap(
            True
        )
        detail_layout.addWidget(
            self.streaming_status
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
        detail_layout.addWidget(
            self.open_local_button
        )

        detail_layout.addWidget(
            QLabel(
                "Trackliste"
            )
        )
        self.track_table = QTableWidget(
            0,
            4,
        )
        self.track_table.setHorizontalHeaderLabels(
            [
                "CD",
                "Track",
                "Titel",
                "Dauer",
            ]
        )
        self.track_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.track_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        detail_layout.addWidget(
            self.track_table,
            stretch=1,
        )

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
                260,
                520,
                650,
            ]
        )
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

    def search_artist(
        self,
        artist_name: str,
    ) -> None:
        artist_name = str(
            artist_name or ""
        ).strip()

        if not artist_name:
            return

        self.search_edit.setText(
            artist_name
        )
        self.search()

    def search(self) -> None:
        query = self.search_edit.text().strip()

        if not query:
            return

        self.search_button.setEnabled(
            False
        )
        self.artist_list.clear()
        self.suggestion_label.clear()
        self.suggestion_label.hide()
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
            finished=self._artists_loaded,
        )

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
            self.group_title.setText(
                "Keine Künstler gefunden"
            )
            self.group_meta.setText(
                (
                    "MusicBrainz lieferte für diese "
                    "Schreibweise keine Treffer. "
                    "Öffne bei Bedarf „Debug“, um "
                    "Anfrage und Antwort zu prüfen."
                )
            )
            self._set_status(
                "Keine Künstler gefunden."
            )
            self.suggestion_label.hide()
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

        if result_type != "musicbrainz_artist":
            return

        self.release_groups = []
        self.musicbrainz_release_groups = []
        self.discogs_release_groups = []
        self.current_artist_name = artist.name
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
        self.group_title.setText(
            artist.name
        )
        self.group_meta.setText(
            "MusicBrainz-Künstler"
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

    def _relations_loaded(self, result) -> None:
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
            "Mitglieder", "Gruppen", "Kollaborationen", "Aliase",
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
                child = QTreeWidgetItem([f"{relation.name}{suffix}"])
                child.setData(0, Qt.ItemDataRole.UserRole, relation)
                details = [relation.relation_type]
                if relation.disambiguation:
                    details.append(relation.disambiguation)
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
        if "alias" in relation_type or relation_type in {"is person", "performance name"}:
            return "Aliase"
        if any(word in relation_type for word in ("producer", "mix", "master", "engineer", "instrument", "vocal")):
            return "Produzenten / Mitwirkende"
        if any(word in relation_type for word in ("collaboration", "collaborated", "supporting musician")):
            return "Kollaborationen"
        return "Weitere"

    def _relation_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        relation = item.data(0, Qt.ItemDataRole.UserRole)
        if relation is None:
            return
        if relation.target_type in {"artist", "alias"}:
            self.search_artist(relation.name)
        elif relation.target_type == "label":
            self._set_status(
                f"MusicBrainz-Label „{relation.name}“ wird geöffnet …"
            )
            webbrowser.open(
                f"https://musicbrainz.org/label/{relation.target_id}"
            )

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

    def _render_alternative_views(self) -> None:
        if not hasattr(self, "release_table"):
            return
        self._view_syncing = True; self.release_table.setSortingEnabled(False)
        self.release_table.setRowCount(len(self.release_groups)); self.cover_model.clear(); self.cover_list.clear()
        cover_size,_ = self._cover_dimensions(); placeholder=QPixmap(cover_size,cover_size); placeholder.fill(Qt.GlobalColor.transparent)
        for row, group in enumerate(self.release_groups):
            source = "Discogs" if group.source == "discogs" else "MusicBrainz"
            local = self.local_album_status.get(_normalized(group.title), "Nein")
            extra = " · ".join([*group.labels[:2],*group.formats[:3]])
            values=(group.title,group.artist,group.first_release_date[:4],_category(group),source,extra,local)
            for col,value in enumerate(values):
                item=QTableWidgetItem(str(value or "")); item.setData(Qt.ItemDataRole.UserRole,row); self.release_table.setItem(row,col,item)
            grid=QStandardItem(QIcon(placeholder), f"{group.title}\n{group.artist or source}\n{group.first_release_date[:4]}")
            grid.setData(row,Qt.ItemDataRole.UserRole); grid.setEditable(False); self.cover_model.appendRow(grid)
            li=QListWidgetItem(QIcon(placeholder), f"{group.title}\n{group.artist or 'Unbekannter Künstler'} · {group.first_release_date[:4] or 'Jahr unbekannt'} · {_category(group)}\n{extra or source}")
            li.setData(Qt.ItemDataRole.UserRole,row); li.setSizeHint(QSize(300,max(76,cover_size+12))); self.cover_list.addItem(li)
            self._load_release_thumbnail(row,group)
        self.release_table.setSortingEnabled(True); self.release_table.resizeColumnsToContents(); self._view_syncing=False

    def _load_release_thumbnail(self, row: int, group: ReleaseGroup) -> None:
        local_file=self.local_album_files.get(_normalized(group.title),"")
        if local_file:
            try: data=load_cover(local_file)
            except Exception: data=None
            if data:
                self._apply_release_thumbnail(row,data); return
        if group.cover_url:
            cache=self.cover_cache_directory / f"view-{group.source}-{group.release_group_id}.jpg"
            self._run(_fetch_url_cover, group.cover_url, cache, finished=lambda data,target=row:self._apply_release_thumbnail(target,data))

    def _apply_release_thumbnail(self, row: int, data: bytes | None) -> None:
        if not data or not (0 <= row < len(self.release_groups)): return
        pix=QPixmap()
        if not pix.loadFromData(data): return
        size,_=self._cover_dimensions(); icon=QIcon(pix.scaled(size,size,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        item=self.cover_model.item(row)
        if item is not None: item.setIcon(icon)
        li=self.cover_list.item(row)
        if li is not None: li.setIcon(icon)

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

    def _load_group(self, group: ReleaseGroup) -> None:
        self.current_group=group; self.editions=[]; self.edition_combo.clear(); self.track_table.setRowCount(0)
        self._cover_generation += 1; self._show_cover(None); self.group_title.setText(group.title)
        key=_normalized(group.title); local_path=self.local_albums.get(key); status=self.local_album_status.get(key,"Nicht vorhanden"); local_online=status == "Lokal verfügbar"
        self.group_meta.setText(" · ".join(v for v in (_type_text(group),group.first_release_date or "Datum unbekannt",status) if v))
        self.open_local_button.setProperty(
            "local_path",
            local_path or "",
        )
        self.open_local_button.setEnabled(bool(local_path) and local_online)
        self.open_local_button.setToolTip(
            "Lokales Album im Tagger öffnen"
            if local_online
            else "Das Album ist indiziert, die Musikquelle ist momentan nicht erreichbar."
        )
        self.streaming_button.setEnabled(True); self.quality_button.setEnabled(True); self.apple_button.setEnabled(False)
        self.streaming_status.setText("Streaming und Qualität wurden nicht abgefragt.")
        if group.source == "discogs" and group.discogs_release_id:
            self._run(self._discogs_edition_from_group,group,finished=self._editions_loaded)
        else:
            self._run(fetch_release_group_editions,group.release_group_id,finished=self._editions_loaded)

    def _groups_loaded(
        self,
        result,
    ) -> None:
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
                        self.local_album_status.get(
                            local_key,
                            "Nein",
                        ),
                    ]
                )
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
        self.track_table.setRowCount(
            len(tracks)
        )

        for row, track in enumerate(
            tracks
        ):
            values = (
                str(
                    track.disc_number
                ),
                f"{track.track_number:02d}",
                _track_title(
                    track
                ),
                _duration(
                    track.length_ms
                ),
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

        self.track_table.resizeColumnsToContents()
        self._set_status(
            f"{len(tracks)} Titel geladen."
        )

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
            _fetch_release_cover,
            edition.release_id,
            self.cover_cache_directory,
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
            "Apple Music wird auf ausdrücklichen Wunsch geprüft …"
        )
        self._run(
            search_apple_album,
            group.title,
            group.artist,
            wanted_year=(
                group.first_release_date[
                    :4
                ]
            ),
            country="DE",
            limit=10,
            finished=self._streaming_loaded,
        )

    def _streaming_loaded(
        self,
        candidates,
    ) -> None:
        self.streaming_button.setEnabled(
            True
        )
        candidates = list(
            candidates
        )

        if not candidates:
            self.streaming_status.setText(
                "Bei Apple Music wurde keine eindeutige Ausgabe gefunden. "
                "Weitere Dienste wurden noch nicht abgefragt."
            )
            return

        best = candidates[
            0
        ]
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
            "Qobuz, TIDAL und Deezer folgen in späteren Ausbaustufen."
        )

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
                item.setText(
                    4,
                    self.local_album_status.get(
                        key,
                        "Nein",
                    ),
                )

    def _run(
        self,
        function,
        *args,
        finished,
        transform=None,
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
        worker.signals.failed.connect(
            self._failed
        )
        worker.signals.failed.connect(
            release
        )
        self.thread_pool.start(
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

    def _set_status(
        self,
        text: str,
    ) -> None:
        self.streaming_status.setText(
            text
        )

def _fetch_discogs_catalog(
    entity_name: str,
    token: str,
    *,
    force_refresh: bool = False,
) -> DiscogsCatalogSnapshot:
    if not force_refresh:
        cached = load_catalog_snapshot(entity_name)
        if cached is not None:
            return cached
    hits = search_catalog(
        entity_name,
        token,
        kinds=("artist", "label"),
        limit_per_kind=10,
    )
    wanted = _normalized(entity_name)
    exact_hits = [
        hit
        for hit in hits
        if _normalized(_discogs_entity_name(hit.title)) == wanted
    ]
    if not exact_hits:
        return save_catalog_snapshot(entity_name, [])
    # A label is the more specific interpretation when Discogs contains both
    # an artist and a label with exactly the requested name.
    hit = min(exact_hits, key=lambda item: 0 if item.kind == "label" else 1)
    if hit.kind == "label":
        releases = fetch_label_releases(
            hit.entity_id,
            token,
            maximum=100,
            label_name=hit.title,
        )
    else:
        releases = fetch_discogs_artist_releases(
            hit.entity_id, token, maximum=100
        )
    return save_catalog_snapshot(entity_name, releases)


def _discogs_entity_name(value: str) -> str:
    return re.sub(r"\s+\(\d+\)$", "", str(value or "")).strip()


def _merge_release_groups(
    musicbrainz_groups: list[ReleaseGroup],
    discogs_groups: list[ReleaseGroup],
) -> list[ReleaseGroup]:
    merged = list(musicbrainz_groups)
    positions = {
        (_normalized(group.title), group.first_release_date[:4]): index
        for index, group in enumerate(merged)
    }
    for discogs_group in discogs_groups:
        key = (
            _normalized(discogs_group.title),
            discogs_group.first_release_date[:4],
        )
        index = positions.get(key)
        if index is None:
            positions[key] = len(merged)
            merged.append(discogs_group)
            continue
        current = merged[index]
        merged[index] = replace(
            current,
            labels=current.labels or discogs_group.labels,
            formats=current.formats or discogs_group.formats,
            badges=tuple(dict.fromkeys((*current.badges, *discogs_group.badges))),
            external_url=current.external_url or discogs_group.external_url,
            cover_url=current.cover_url or discogs_group.cover_url,
            discogs_release_id=(
                current.discogs_release_id
                or discogs_group.discogs_release_id
            ),
        )
    return sorted(
        merged,
        key=lambda group: (
            group.first_release_date or "9999",
            group.title.casefold(),
        ),
    )


def _fetch_url_cover(
    url: str,
    cache_path: Path,
) -> bytes | None:
    if cache_path.is_file():
        try:
            return cache_path.read_bytes()
        except OSError:
            pass

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "MusicTagStudio/0.7.3.0 "
                "(https://github.com/pcblizzard/MusicTagStudio)"
            )
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=12,
        ) as response:
            data = response.read()
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
    ):
        return None

    if data:
        try:
            cache_path.write_bytes(
                data
            )
        except OSError:
            pass

    return data or None


def _fetch_release_cover(
    release_id: str,
    cache_directory: Path,
) -> bytes | None:
    cache_path = (
        cache_directory
        / f"{release_id}.jpg"
    )

    if cache_path.is_file():
        try:
            return cache_path.read_bytes()
        except OSError:
            pass

    request = urllib.request.Request(
        (
            "https://coverartarchive.org/"
            f"release/{release_id}/front-250"
        ),
        headers={
            "User-Agent": (
                "MusicTagStudio/0.7.2.1 "
                "(https://github.com/pcblizzard/MusicTagStudio)"
            )
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=12,
        ) as response:
            data = response.read()
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
    ):
        return None

    if not data:
        return None

    try:
        cache_path.write_bytes(
            data
        )
    except OSError:
        pass

    return data


def _normalized(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(
            value or ""
        ).casefold(),
    )


def _category(
    group: ReleaseGroup,
) -> str:
    if group.category:
        return group.category

    secondary = {
        value.casefold()
        for value in group.secondary_types
    }

    if "live" in secondary:
        return "Live"

    if "soundtrack" in secondary:
        return "Soundtracks"

    if "compilation" in secondary:
        return "Compilations"

    mapping = {
        "Album": "Alben",
        "EP": "EPs",
        "Single": "Singles",
        "Broadcast": "Sonstiges",
    }

    return mapping.get(
        group.primary_type,
        "Sonstiges",
    )



def _artist_text(
    artist: ArtistCandidate,
) -> str:
    details: list[str] = []

    if artist.country:
        details.append(
            artist.country
        )

    if artist.artist_type:
        details.append(
            artist.artist_type
        )

    if artist.disambiguation:
        details.append(
            artist.disambiguation
        )

    if not details:
        return artist.name

    return (
        f"{artist.name} "
        f"({' · '.join(details)})"
    )

def _category_order(
    category: str,
) -> int:
    order = {
        "Alben": 0,
        "Live": 1,
        "EPs": 2,
        "Singles": 3,
        "Mixtapes": 4,
        "Sampler": 5,
        "Compilations": 6,
        "Soundtracks": 7,
        "Boxsets": 8,
        "Bootlegs": 9,
        "Sonstiges": 10,
    }

    return order.get(
        category,
        99,
    )


def _medium_count(
    formats: tuple[str, ...],
) -> int:
    total = 0

    for value in formats:
        match = re.match(
            r"(\d+)×",
            value,
        )
        total += (
            int(
                match.group(1)
            )
            if match
            else 1
        )

    return max(
        1,
        total,
    )


def _discogs_position(
    value: str,
    fallback: int,
) -> tuple[int, int]:
    value = str(
        value or ""
    ).strip()
    match = re.match(
        r"(\d+)[-.](\d+)",
        value,
    )

    if match:
        return (
            int(
                match.group(1)
            ),
            int(
                match.group(2)
            ),
        )

    numbers = re.findall(
        r"\d+",
        value,
    )

    if numbers:
        return (
            1,
            int(
                numbers[-1]
            ),
        )

    return (
        1,
        fallback,
    )


def _duration_ms(
    value: str,
) -> int | None:
    parts = str(
        value or ""
    ).split(
        ":"
    )

    try:
        if len(parts) == 2:
            return (
                int(
                    parts[0]
                )
                * 60
                + int(
                    parts[1]
                )
            ) * 1000

        if len(parts) == 3:
            return (
                int(
                    parts[0]
                )
                * 3600
                + int(
                    parts[1]
                )
                * 60
                + int(
                    parts[2]
                )
            ) * 1000
    except ValueError:
        return None

    return None


def _type_text(
    group: ReleaseGroup,
) -> str:
    values = [
        group.primary_type,
        *group.secondary_types,
    ]

    return ", ".join(
        value
        for value in values
        if value
    ) or "Unbekannt"


def _track_title(
    track: Track,
) -> str:
    if track.artist:
        return (
            f"{track.title} — "
            f"{track.artist}"
        )

    return track.title


def _duration(
    length_ms: int | None,
) -> str:
    if not length_ms:
        return ""

    seconds = round(
        length_ms / 1000
    )

    return (
        f"{seconds // 60}:"
        f"{seconds % 60:02d}"
    )
