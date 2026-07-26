from __future__ import annotations

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QSize,
    QThreadPool,
    Signal,
    Slot,
)
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..direct_album_lookup import (
    AlbumMatchingResult,
    build_album_matching_result,
    is_prerelease_date,
    lookup_album,
)
from ..direct_references import (
    DirectAlbumReferenceError,
    parse_album_reference,
)
from ..i18n import tr
from ..models.song import Song
from ..icons import make_icon
from ..player.preview import PreviewPlayer
from .formatting import localized_date


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class LookupWorker(QRunnable):
    def __init__(
        self,
        reference,
        apple_country: str,
    ):
        super().__init__()
        self.reference = reference
        self.apple_country = apple_country
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = lookup_album(
                self.reference,
                apple_country=self.apple_country,
            )
        except Exception as error:
            self.signals.failed.emit(
                str(error)
            )
            return

        self.signals.finished.emit(result)


class DirectAlbumDialog(QDialog):
    def __init__(
        self,
        songs: list[Song],
        apple_country: str,
        parent=None,
        *,
        language: str = "automatic",
    ):
        super().__init__(parent)

        self.language = language
        self.songs = songs
        self.apple_country = apple_country
        self.result = None
        self.matching_result: (
            AlbumMatchingResult | None
        ) = None
        self.matches: dict = {}
        self.reference = None
        self.track_combos: list[
            QComboBox
        ] = []
        self.preview_buttons: list[
            QPushButton
        ] = []
        self._playing_preview_row = -1
        self.preview_player = PreviewPlayer(self)
        self.preview_player.state_changed.connect(
            self._on_preview_state
        )
        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self.setWindowTitle(
            tr("direct_album_title", language)
        )
        self.resize(
            1250,
            720,
        )

        layout = QVBoxLayout(self)

        info = QLabel(
            tr("direct_album_info", language)
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(
            tr("direct_album_placeholder", language)
        )
        self.load_button = QPushButton(
            tr("load_metadata_btn", language)
        )
        self.load_button.clicked.connect(
            self._load
        )
        input_layout.addWidget(
            self.input_edit,
            1,
        )
        input_layout.addWidget(
            self.load_button,
        )
        layout.addLayout(input_layout)

        self.status_label = QLabel(
            tr("no_album_loaded", language)
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(
            self.status_label
        )

        self.table = QTableWidget(
            len(songs),
            8,
        )
        self.table.setHorizontalHeaderLabels(
            [
                tr("col_local_file", language),
                tr("col_local_title", language),
                tr("col_local_track", language),
                tr("col_mapped_track", language),
                tr("col_source_title", language),
                tr("col_confidence", language),
                tr("col_reason", language),
                tr("col_preview", language),
            ]
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )

        for column in (
            1,
            2,
            3,
            5,
            6,
            7,
        ):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        layout.addWidget(
            self.table
        )

        for row, song in enumerate(songs):
            self.table.setItem(
                row,
                0,
                QTableWidgetItem(song.path),
            )
            self.table.setItem(
                row,
                1,
                QTableWidgetItem(song.title),
            )
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(
                    f"{song.disc or '1'}/{song.track}"
                ),
            )

        buttons = QDialogButtonBox()
        self.compare_button = QPushButton(
            tr("compare_metadata", language)
        )
        cancel = QPushButton(
            tr("cancel", language)
        )
        buttons.addButton(
            self.compare_button,
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        buttons.addButton(
            cancel,
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.compare_button.setEnabled(False)
        self.compare_button.clicked.connect(
            self._accept
        )
        cancel.clicked.connect(
            self.reject
        )
        layout.addWidget(buttons)

    def _load(self):
        try:
            reference = parse_album_reference(
                self.input_edit.text()
            )
        except DirectAlbumReferenceError as error:
            QMessageBox.warning(
                self,
                tr("invalid_link_title", self.language),
                str(error),
            )
            return

        if (
            reference.reference_type
            == "song"
            and len(self.songs) != 1
        ):
            QMessageBox.warning(
                self,
                tr("song_link_needs_file_title", self.language),
                tr("song_link_needs_file_msg", self.language),
            )
            return

        self.reference = reference
        self.load_button.setEnabled(False)
        self.compare_button.setEnabled(False)
        self.status_label.setText(
            tr("album_loading", self.language)
        )

        worker = LookupWorker(
            reference,
            self.apple_country,
        )
        worker.signals.finished.connect(
            self._loaded
        )
        worker.signals.failed.connect(
            self._failed
        )
        self.thread_pool.start(worker)

    def _loaded(
        self,
        result,
    ):
        self.load_button.setEnabled(True)
        self.result = result
        self.matching_result = (
            build_album_matching_result(
                self.songs,
                result,
            )
        )
        automatic_by_local = {
            match.local_index: match
            for match
            in self.matching_result.matches
        }

        self.track_combos.clear()
        self.preview_player.stop()
        self._playing_preview_row = -1
        self.preview_buttons.clear()

        for row, song in enumerate(
            self.songs
        ):
            match = automatic_by_local.get(
                row
            )
            combo = QComboBox()
            combo.addItem(
                tr("do_not_map", self.language),
                -1,
            )

            for track_index, track in enumerate(
                result.tracks
            ):
                combo.addItem(
                    tr(
                        "combo_track_line",
                        self.language,
                        disc=track.disc or "1",
                        track=track.track,
                        title=self._track_display(track, self.language),
                    ),
                    track_index,
                )

            if match is not None:
                combo.setCurrentIndex(
                    combo.findData(
                        match.track_index
                    )
                )

            combo.currentIndexChanged.connect(
                self._manual_mapping_changed
            )
            self.track_combos.append(combo)
            self.table.setCellWidget(
                row,
                3,
                combo,
            )

            preview_button = QPushButton()
            self._set_preview_button_icon(preview_button, "play")
            preview_button.setToolTip(
                tr("preview_tip", self.language)
            )
            preview_button.clicked.connect(
                lambda _checked=False, index=row: self._toggle_preview(index)
            )
            self.preview_buttons.append(preview_button)
            self.table.setCellWidget(
                row,
                7,
                preview_button,
            )

            if match is None:
                self.table.setItem(
                    row,
                    4,
                    QTableWidgetItem(""),
                )
                self.table.setItem(
                    row,
                    5,
                    QTableWidgetItem(
                        "Nicht zugeordnet"
                    ),
                )
                self.table.setItem(
                    row,
                    6,
                    QTableWidgetItem(""),
                )
                continue

            self.table.setItem(
                row,
                4,
                QTableWidgetItem(
                    self._track_display(match.track, self.language)
                ),
            )
            self.table.setItem(
                row,
                5,
                QTableWidgetItem(
                    match.confidence
                ),
            )
            self.table.setItem(
                row,
                6,
                QTableWidgetItem(
                    ", ".join(
                        match.reasons
                    )
                ),
            )

        self._rebuild_manual_matches()
        self._refresh_preview_buttons()

        automatic_count = len(
            self.matching_result.matches
        )
        ambiguous_count = len(
            self.matching_result
            .ambiguous_local_indexes
        )

        self.status_label.setText(
            tr(
                "mapping_summary",
                self.language,
                artist=result.album_artist,
                album=result.album,
                auto=automatic_count,
                total=len(self.songs),
                ambiguous=ambiguous_count,
                note=self._prerelease_note(result, self.language),
            )
        )

    @staticmethod
    def _track_display(track, language: str = "automatic") -> str:
        """Titel plus Hinweis, wenn der Track noch nicht veröffentlicht ist.

        Bei Vorabveröffentlichungen liefert Apple für noch nicht erschienene
        Titel Platzhalter wie „Track 2"; diese werden hier gekennzeichnet.
        """
        if not getattr(track, "is_streamable", True):
            return tr("track_not_released", language, title=track.title)
        return str(track.title)

    @staticmethod
    def _prerelease_note(result, language: str = "automatic") -> str:
        """Zusatzhinweis für Vorabveröffentlichungen (tagesgenaues Zukunftsdatum)."""
        release_date = getattr(result, "release_date", "")
        if not is_prerelease_date(release_date):
            return ""
        day = localized_date(release_date)
        return tr("prerelease_note", language, day=day)

    def _manual_mapping_changed(self):
        if self.result is None:
            return

        sender = self.sender()

        try:
            row = self.track_combos.index(
                sender
            )
        except ValueError:
            return

        track_index = sender.currentData()

        if (
            track_index is None
            or track_index < 0
        ):
            self.table.setItem(
                row,
                4,
                QTableWidgetItem(""),
            )
            self.table.setItem(
                row,
                5,
                QTableWidgetItem(
                    tr("not_mapped", self.language)
                ),
            )
        else:
            track = self.result.tracks[
                track_index
            ]
            self.table.setItem(
                row,
                4,
                QTableWidgetItem(
                    self._track_display(track, self.language)
                ),
            )
            self.table.setItem(
                row,
                5,
                QTableWidgetItem(
                    tr("manually_confirmed", self.language)
                ),
            )

        self._rebuild_manual_matches()
        self._refresh_preview_buttons()

    def _selected_track(self, row: int):
        if self.result is None or row >= len(self.track_combos):
            return None

        track_index = self.track_combos[row].currentData()

        if track_index is None or track_index < 0:
            return None

        return self.result.tracks[track_index]

    def _toggle_preview(self, row: int) -> None:
        track = self._selected_track(row)

        if track is None or not track.preview_url:
            return

        # Zeilenbasierte Steuerung: derselbe Album-Track kann mehreren
        # lokalen Dateien zugeordnet sein und hätte dann dieselbe URL.
        if row == self._playing_preview_row and self.preview_player.is_playing():
            self._playing_preview_row = -1
            self.preview_player.stop()
            return

        self._playing_preview_row = row
        self.preview_player.play(track.preview_url, track.title)

    def _refresh_preview_buttons(self) -> None:
        """Aktiviert den ▶-Knopf nur, wenn der zugeordnete Track eine
        Vorschau-URL hat (Apple/Deezer – MusicBrainz/Discogs liefern keine)."""
        playing = self.preview_player.is_playing()

        for row, button in enumerate(self.preview_buttons):
            track = self._selected_track(row)
            has_preview = bool(track and track.preview_url)
            button.setEnabled(has_preview)
            is_active = playing and row == self._playing_preview_row
            self._set_preview_button_icon(button, "pause" if is_active else "play")

    def _set_preview_button_icon(self, button: QPushButton, name: str) -> None:
        """Setzt das SVG-Play/Pause-Icon (Palette-Farbe) samt previewState."""
        color = self.palette().color(QPalette.ColorRole.ButtonText).name()
        button.setIcon(make_icon(name, color))
        button.setIconSize(QSize(16, 16))
        button.setProperty("previewState", name)

    def _on_preview_state(self, _url: str, _playing: bool) -> None:
        self._refresh_preview_buttons()

    def done(self, result: int) -> None:
        self.preview_player.stop()
        super().done(result)

    def _rebuild_manual_matches(self):
        if self.result is None:
            self.matches = {}
            self.compare_button.setEnabled(
                False
            )
            return

        matches = {}
        used_track_indexes = []
        missing_rows = []

        for row, combo in enumerate(
            self.track_combos
        ):
            track_index = combo.currentData()

            if (
                track_index is None
                or track_index < 0
            ):
                missing_rows.append(row)
                continue

            matches[row] = (
                self.result.tracks[
                    track_index
                ]
            )
            used_track_indexes.append(
                track_index
            )

        duplicates = {
            track_index
            for track_index
            in used_track_indexes
            if used_track_indexes.count(
                track_index
            ) > 1
        }

        self.matches = matches
        complete = (
            len(matches) == len(self.songs)
            and not duplicates
        )
        self.compare_button.setEnabled(
            complete
        )

        if duplicates:
            duplicate_text = ", ".join(
                str(
                    self.result.tracks[
                        index
                    ].track
                )
                for index in sorted(
                    duplicates
                )
            )
            self.status_label.setText(
                tr("one_to_one_required", self.language, tracks=duplicate_text)
            )
        elif missing_rows:
            self.status_label.setText(
                tr("unmapped_files", self.language, count=len(missing_rows))
            )

    def _failed(
        self,
        message: str,
    ):
        self.load_button.setEnabled(True)
        self.status_label.setText(
            tr("album_load_failed", self.language, message=message)
        )

    def _accept(self):
        if (
            self.result is None
            or len(self.matches)
            != len(self.songs)
        ):
            QMessageBox.warning(
                self,
                tr("mapping_incomplete_title", self.language),
                tr("mapping_incomplete_msg", self.language),
            )
            return

        self.accept()
