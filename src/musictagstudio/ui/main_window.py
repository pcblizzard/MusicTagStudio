from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.merger import apply_merged_metadata, song_values
from ..models.song import Song
from ..services.cover import (
    covers_are_identical,
    load_cover,
    load_cover_info,
)
from ..services.metadata_io import save_song_metadata
from ..services.proposal import (
    build_batch_proposals,
    build_proposal,
)
from ..services.scanner import scan_folder_detailed
from ..settings import load_settings, save_settings
from ..theme import (
    BUTTON_CHANGED,
    BUTTON_NORMAL,
    INPUT_CHANGED,
    INPUT_NORMAL,
    apply_theme,
)
from ..batch_comparison_logic import BatchSongProposal
from .batch_dialog import BatchComparisonDialog
from .comparison_dialog import ComparisonDialog
from .settings_dialog import SettingsDialog
from .cover_dialog import CoverSelectionDialog
from .direct_album_dialog import DirectAlbumDialog
from .audio_analysis_dialog import AudioAnalysisDialog
from .batch_cover_dialog import BatchCoverDialog
from .library_audit_dialog import LibraryAuditDialog
from ..cover_management.batch import build_album_cover_plans
from ..cover_management.manager import CoverManager


DEFAULT_MUSIC_FOLDER = (
    r"C:\Users\Michael\Music\Stieber Twins\Stieber Twins"
    r"\Stieber Twins - Fenster zum Hof"
)

COVER_SIZE = 280
MIXED_VALUE_PLACEHOLDER = "<verschiedene Werte>"
OPTIONAL_FIELDS = (
    "isrc",
    "label",
    "copyright",
    "composer",
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MusicTagStudio")
        self.resize(1500, 780)

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

        self.create_ui()
        self.create_menu()

    def create_ui(self):
        container = QWidget()
        container_layout = QVBoxLayout(container)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.folder_label = QLabel(f"Ordner: {self.folder}")

        self.select_button = QPushButton(
            "Musikordner auswählen"
        )
        self.select_button.clicked.connect(self.select_folder)

        self.scan_button = QPushButton(
            "Audiodateien scannen"
        )
        self.scan_button.clicked.connect(self.scan_music)

        provider_buttons = QHBoxLayout()

        self.proposal_button = QPushButton(
            "Vorschlag für ausgewählten Titel"
        )
        self.proposal_button.clicked.connect(
            self.create_single_proposal
        )
        self.proposal_button.setEnabled(False)

        self.batch_button = QPushButton(
            "Vorschläge für markierte Titel"
        )
        self.batch_button.clicked.connect(
            self.create_batch_proposals
        )
        self.batch_button.setEnabled(False)

        self.cover_button = QPushButton(
            "Cover für Auswahl verwalten"
        )
        self.cover_button.clicked.connect(
            self.manage_cover
        )
        self.cover_button.setEnabled(False)

        self.direct_album_button = QPushButton(
            "Album-/Song-Link oder ID laden"
        )
        self.direct_album_button.clicked.connect(
            self.load_direct_album
        )
        self.direct_album_button.setEnabled(False)

        provider_buttons.addWidget(self.proposal_button)
        provider_buttons.addWidget(self.batch_button)
        provider_buttons.addWidget(self.cover_button)
        provider_buttons.addWidget(
            self.direct_album_button
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
            "path",
        )

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.table_fields))
        self.table.setHorizontalHeaderLabels(
            [
                "Track",
                "Titel",
                "Künstler",
                "Album",
                "Disc",
                "Jahr",
                "ISRC",
                "Label",
                "Copyright",
                "Komponist",
                "Datei",
            ]
        )

        self.table.itemSelectionChanged.connect(
            self.handle_selection_changed
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

        for index, field_name in enumerate(self.table_fields):
            if field_name in {"title", "artist", "album"}:
                mode = QHeaderView.ResizeMode.Stretch
            elif field_name == "path":
                mode = QHeaderView.ResizeMode.Interactive
            else:
                mode = QHeaderView.ResizeMode.ResizeToContents

            header.setSectionResizeMode(index, mode)

        self.table.setColumnWidth(
            self.table_fields.index("path"),
            240,
        )

        left_layout.addWidget(self.folder_label)
        left_layout.addWidget(self.select_button)
        left_layout.addWidget(self.scan_button)
        left_layout.addLayout(provider_buttons)
        left_layout.addWidget(self.table)

        right_widget = QWidget()
        right_widget.setFixedWidth(420)
        right_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_widget)

        self.selection_label = QLabel(
            "Kein Titel ausgewählt"
        )
        self.selection_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        right_layout.addWidget(self.selection_label)

        self.cover_label = QLabel("Kein Cover vorhanden")
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
            "title": "Titel:",
            "artist": "Künstler:",
            "album_artist": "Albumkünstler:",
            "album": "Album:",
            "genre": "Genre:",
            "year": "Jahr:",
            "isrc": "ISRC:",
            "label": "Label:",
            "copyright": "Copyright:",
            "composer": "Komponist:",
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

        right_layout.addWidget(form_widget)
        right_layout.addStretch()

        self.splitter = QSplitter(
            Qt.Orientation.Horizontal
        )
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([1080, 420])

        container_layout.addWidget(self.splitter)
        self.setCentralWidget(container)

        self.update_optional_columns()

    def create_menu(self):
        analysis_menu = self.menuBar().addMenu(
            "Audio-Analyse"
        )

        analysis_action = analysis_menu.addAction(
            "Analyse öffnen …"
        )
        analysis_action.triggered.connect(
            self.open_audio_analysis
        )

        audit_menu = self.menuBar().addMenu(
            "Bibliotheksprüfung"
        )

        audit_action = audit_menu.addAction(
            "Prüfung öffnen …"
        )
        audit_action.triggered.connect(
            self.open_library_audit
        )

        settings_menu = self.menuBar().addMenu(
            "Einstellungen"
        )

        settings_action = settings_menu.addAction(
            "Optionen …"
        )
        settings_action.triggered.connect(
            self.open_settings
        )

    def open_library_audit(self):
        selected_rows = self.selected_rows()
        selected_songs = [
            self.songs[row]
            for row in selected_rows
            if 0 <= row < len(self.songs)
        ]

        dialog = LibraryAuditDialog(
            selected_songs,
            self.songs,
            self,
        )
        dialog.exec()

    def open_audio_analysis(self):
        selected_rows = self.selected_rows()
        selected_songs = [
            self.songs[row]
            for row in selected_rows
            if 0 <= row < len(self.songs)
        ]

        dialog = AudioAnalysisDialog(
            selected_songs,
            self.songs,
            self,
        )
        dialog.exec()

    def open_settings(self):
        current_settings = load_settings()
        dialog = SettingsDialog(
            current_settings,
            self,
        )

        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        new_settings = dialog.selected_settings()
        save_settings(new_settings)

        app = QApplication.instance()

        if isinstance(app, QApplication):
            apply_theme(
                app,
                new_settings.theme,
            )

    def select_folder(self):
        if not self.confirm_pending_changes():
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Musikordner auswählen",
            self.folder or "",
        )

        if folder:
            self.folder = folder
            self.folder_label.setText(
                f"Ordner: {folder}"
            )

    def scan_music(self):
        if not self.confirm_pending_changes():
            return

        if not self.folder or not Path(self.folder).is_dir():
            QMessageBox.warning(
                self,
                "Ordner nicht gefunden",
                (
                    "Der Musikordner wurde nicht gefunden:"
                    f"\n\n{self.folder or ''}"
                ),
            )
            return

        scan_result = scan_folder_detailed(
            self.folder
        )
        self.songs = list(
            scan_result.songs
        )

        if scan_result.failures:
            details = "\n\n".join(
                f"{failure.path}\n{failure.error}"
                for failure
                in scan_result.failures[:20]
            )

            if len(scan_result.failures) > 20:
                details += (
                    "\n\n"
                    f"… und {len(scan_result.failures) - 20} "
                    "weitere Datei(en)."
                )

            QMessageBox.warning(
                self,
                "Einige Audiodateien wurden übersprungen",
                (
                    f"Erkannt: {scan_result.detected_files}\n"
                    f"Eingelesen: {scan_result.successful_files}\n"
                    f"Übersprungen: {len(scan_result.failures)}"
                    f"\n\n{details}"
                    "\n\nVollständige technische Details stehen in "
                    "logs/scanner.log und logs/wavpack.log."
                ),
            )
        elif (
            scan_result.detected_files == 0
        ):
            QMessageBox.information(
                self,
                "Keine Audiodateien gefunden",
                (
                    "Im gewählten Ordner wurden keine "
                    "unterstützten Audiodateien gefunden.\n\n"
                    "Unterstützte Endungen:\n"
                    ".flac, .wv, .mp3, .ogg, .oga, "
                    ".opus, .m4a und .mp4"
                ),
            )
        self.current_row = -1
        self.active_rows = []
        self.previous_rows = []

        self.clear_editor()

        self.table.blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(self.songs))

        for row, song in enumerate(self.songs):
            self.update_table_row(row, song)

        self.table.blockSignals(False)
        self.update_optional_columns()

        enabled = bool(self.songs)
        self.proposal_button.setEnabled(enabled)
        self.batch_button.setEnabled(enabled)
        self.cover_button.setEnabled(enabled)
        self.direct_album_button.setEnabled(enabled)

        if enabled:
            self.table.selectRow(0)
            self.table.setCurrentCell(0, 0)
            self.handle_selection_changed()
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
            f"1 Titel · {song.album or 'ohne Album'}"
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
        album_word = "Album" if album_count == 1 else "Alben"
        self.selection_label.setText(f"{len(rows)} Titel · {album_count} {album_word}")
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
            )
            dialog.exec()
            self.refresh_active_editor()
            return

        dialog = CoverSelectionDialog(
            manager,
            songs[0],
            self,
        )

        if (
            dialog.exec()
            != dialog.DialogCode.Accepted
            or dialog.selected_candidate
            is None
        ):
            return

        QApplication.setOverrideCursor(
            Qt.CursorShape.WaitCursor
        )

        try:
            result = manager.apply(
                dialog.selected_candidate,
                songs,
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "Cover-Verarbeitung fehlgeschlagen",
                str(error),
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.refresh_active_editor()

        QMessageBox.information(
            self,
            "Cover gespeichert",
            (
                f"Master: {result.master_path}\n\n"
                f"400-px-Cover: "
                f"{result.folder_cover_path}\n\n"
                f"In {result.embedded_files} "
                "Audiodateien eingebettet."
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
        )

        if (
            comparison.exec()
            != comparison.DialogCode.Accepted
        ):
            return

        saved = 0
        failed: list[str] = []

        for song_row, updates in (
            comparison.selected_updates.items()
        ):
            song = self.songs[song_row]
            updated = replace(
                song,
                **updates,
            )

            try:
                save_song_metadata(
                    updated.path,
                    updated,
                )
            except Exception as error:
                failed.append(
                    f"{song.title}: {error}"
                )
                continue

            self.songs[song_row] = updated
            self.update_table_row(
                song_row,
                updated,
            )
            saved += 1

        self.update_optional_columns()
        self.refresh_active_editor()

        message = (
            f"{saved} Titel wurden über den direkten "
            "Album-Link aktualisiert."
        )

        if failed:
            message += (
                "\n\nFehler:\n"
                + "\n".join(failed)
            )

        QMessageBox.information(
            self,
            "Direkte Albumabfrage abgeschlossen",
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

    def create_batch_proposals(self):
        if self.has_unsaved_changes:
            if not self.confirm_pending_changes():
                return

        rows = self.selected_rows()

        if not rows:
            rows = list(range(len(self.songs)))

        progress = QProgressDialog(
            "Metadatenanbieter werden abgefragt …",
            "Abbrechen",
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
        )

        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        saved = 0
        failed: list[str] = []

        for song_row, updates in (
            dialog.selected_updates.items()
        ):
            song = self.songs[song_row]
            updated = replace(
                song,
                **updates,
            )

            try:
                save_song_metadata(
                    updated.path,
                    updated,
                )
            except Exception as error:
                failed.append(
                    f"{song.title}: {error}"
                )
                continue

            self.songs[song_row] = updated
            self.update_table_row(
                song_row,
                updated,
            )
            saved += 1

        self.update_optional_columns()

        message = f"{saved} Titel wurden gespeichert."

        if failed:
            message += (
                "\n\nFehler:\n"
                + "\n".join(failed)
            )

        QMessageBox.information(
            self,
            "Batch-Verarbeitung abgeschlossen",
            message,
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
                f"Änderungen auf {count} Titel anwenden"
                f"{suffix}"
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

        try:
            save_song_metadata(
                updated.path,
                updated,
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "Speichern fehlgeschlagen",
                str(error),
            )
            return

        self.songs[row] = updated
        self.update_table_row(row, updated)
        self.update_optional_columns()

        self.original_values = values.copy()
        self.update_dirty_state()

        QMessageBox.information(
            self,
            "Gespeichert",
            "Metadaten wurden gespeichert.",
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
            "Mehrfachbearbeitung bestätigen",
            (
                f"Die markierten Felder werden auf "
                f"{len(rows)} Titel angewendet.\n\n"
                "Nicht bearbeitete Felder und individuelle "
                "Tracknummern bleiben unverändert."
            ),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if answer != QMessageBox.StandardButton.Save:
            return

        edited_values = self.get_editor_values()
        saved_rows: list[int] = []
        failed: list[str] = []

        for row in rows:
            updates = {
                name: edited_values[name]
                for name in touched_fields
            }
            updated = replace(
                self.songs[row],
                **updates,
            )

            try:
                save_song_metadata(
                    updated.path,
                    updated,
                )
            except Exception as error:
                failed.append(
                    f"{self.songs[row].title}: {error}"
                )
                continue

            self.songs[row] = updated
            self.update_table_row(row, updated)
            saved_rows.append(row)

        self.update_optional_columns()

        if saved_rows:
            self.display_multiple_songs(rows)

        message = (
            f"{len(saved_rows)} von {len(rows)} "
            "Titeln wurden aktualisiert."
        )

        if failed:
            message += (
                "\n\nFehler:\n"
                + "\n".join(failed)
            )

        QMessageBox.information(
            self,
            "Mehrfachbearbeitung abgeschlossen",
            message,
        )

    def confirm_pending_changes(self) -> bool:
        if not self.has_unsaved_changes:
            return True

        count = len(self.active_rows)

        if count > 1:
            message = (
                f"Die Änderungen für {count} Titel "
                "wurden noch nicht gespeichert."
            )
        else:
            message = (
                "Die Änderungen wurden noch nicht gespeichert."
            )

        answer = QMessageBox.warning(
            self,
            "Ungespeicherte Änderungen",
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

    def update_table_row(
        self,
        row: int,
        song: Song,
    ):
        track = (
            f"{song.track}/{song.total_tracks}"
            if song.total_tracks
            else song.track
        )
        disc = (
            f"{song.disc}/{song.total_discs}"
            if song.total_discs
            else song.disc
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
            "Kein Titel ausgewählt"
        )
        self.save_button.setEnabled(False)
        self.save_button.setText(BUTTON_NORMAL)

        self.cover_label.clear()
        self.cover_label.setText(
            "Kein Cover vorhanden"
        )

    def closeEvent(self, event: QCloseEvent):
        if self.confirm_pending_changes():
            event.accept()
        else:
            event.ignore()
