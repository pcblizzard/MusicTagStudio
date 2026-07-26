from __future__ import annotations

import webbrowser

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..i18n import tr
from ..lyrics.search import LyricsSearchResult, search_lyrics
from ..models.song import Song
from ..secret_store import GENIUS_ACCESS_TOKEN, get_secret
from .cover_dialog import FunctionWorker


class LyricsSearchDialog(QDialog):
    def __init__(
        self,
        songs: tuple[Song, ...],
        parent=None,
        *,
        player_bar=None,
        language: str = "automatic",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.songs = songs
        self.player_bar = player_bar
        self.thread_pool = QThreadPool(self)
        self.worker: FunctionWorker | None = None
        self.results: list[LyricsSearchResult] = []

        self.setWindowTitle(tr("lyrics_search", language))
        self.resize(980, 560)
        layout = QVBoxLayout(self)
        intro = QLabel(
            tr("lyrics_search_intro", language)
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        search_row = QHBoxLayout()
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText(
            tr("lyrics_search_placeholder", language)
        )
        self.search_button = QPushButton(tr("search", language))
        search_row.addWidget(self.query_edit, 1)
        search_row.addWidget(self.search_button)
        layout.addLayout(search_row)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [
                tr("col_source", language),
                tr("col_title", language),
                tr("col_artist", language),
                tr("col_album", language),
                tr("col_excerpt", language),
            ]
        )
        excerpt_header = self.table.horizontalHeaderItem(4)
        if excerpt_header is not None:
            excerpt_header.setToolTip(
                tr("excerpt_tip", language)
            )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        for column in range(4):
            header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        action_row = QHBoxLayout()
        self.play_button = QPushButton(tr("play_local", language))
        self.open_button = QPushButton(tr("open_genius", language))
        self.play_button.setEnabled(False)
        self.open_button.setEnabled(False)
        action_row.addWidget(self.play_button)
        action_row.addWidget(self.open_button)
        action_row.addStretch(1)
        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        action_row.addWidget(close_buttons)
        layout.addLayout(action_row)

        self.search_button.clicked.connect(self._start_search)
        self.query_edit.returnPressed.connect(self._start_search)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(self._activate_result)
        self.play_button.clicked.connect(self._play_selected)
        self.open_button.clicked.connect(self._open_selected)

        if not get_secret(GENIUS_ACCESS_TOKEN):
            self.status_label.setText(
                tr("no_genius_token", language)
            )

    def _start_search(self) -> None:
        query = self.query_edit.text().strip()
        if len(query) < 3:
            self.status_label.setText(
                tr("min_chars", self.language)
            )
            return
        self.search_button.setEnabled(False)
        self.table.setRowCount(0)
        self.results.clear()
        self.status_label.setText(tr("lyrics_searching", self.language))
        self.worker = FunctionWorker(
            search_lyrics,
            query,
            songs=self.songs,
            genius_access_token=get_secret(GENIUS_ACCESS_TOKEN),
        )
        self.worker.signals.finished.connect(self._show_results)
        self.worker.signals.failed.connect(self._show_error)
        self.thread_pool.start(self.worker)

    def _show_results(self, results: list[LyricsSearchResult]) -> None:
        self.search_button.setEnabled(True)
        self.results = list(results)
        self.table.setRowCount(len(self.results))
        for row, result in enumerate(self.results):
            values = (
                result.source,
                result.title,
                result.artist,
                result.album,
                result.excerpt,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, column, item)
        if self.results:
            self.table.selectRow(0)
            local_count = sum(bool(item.local_path) for item in self.results)
            genius_count = sum(item.source == "Genius" for item in self.results)
            status = tr(
                "lyrics_hits",
                self.language,
                count=len(self.results),
                local=local_count,
                genius=genius_count,
            )
            if local_count == 0 and genius_count:
                status += tr("lyrics_no_embedded", self.language)
            self.status_label.setText(status)
        else:
            self.status_label.setText(tr("no_songs_found", self.language))

    def _show_error(self, message: str) -> None:
        self.search_button.setEnabled(True)
        self.status_label.setText(
            tr("lyrics_search_failed", self.language, message=message)
        )

    def _selected_result(self) -> LyricsSearchResult | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.results):
            return self.results[row]
        return None

    def _selection_changed(self) -> None:
        result = self._selected_result()
        self.play_button.setEnabled(bool(result and result.local_path))
        self.open_button.setEnabled(bool(result and result.external_url))

    def _activate_result(self, _row: int, _column: int) -> None:
        result = self._selected_result()
        if result and result.local_path:
            self._play_selected()
        elif result and result.external_url:
            self._open_selected()

    def _play_selected(self) -> None:
        result = self._selected_result()
        if result is None or not result.local_path or self.player_bar is None:
            return
        for song in self.songs:
            if song.path == result.local_path:
                self.player_bar.play_songs([song])
                return
        QMessageBox.information(
            self,
            tr("title_unavailable_title", self.language),
            tr("title_unavailable_msg", self.language),
        )

    def _open_selected(self) -> None:
        result = self._selected_result()
        if result and result.external_url:
            webbrowser.open(result.external_url)
