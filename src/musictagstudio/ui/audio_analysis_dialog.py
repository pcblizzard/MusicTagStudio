from __future__ import annotations

import os
import time
from collections import defaultdict
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from pathlib import Path
from threading import Event

from PySide6.QtCore import (
    QByteArray,
    QObject,
    QRunnable,
    QThread,
    QThreadPool,
    Signal,
    Slot,
    Qt,
)
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..audio_analysis.album_check import (
    group_results_by_album,
    signature_text,
)
from ..audio_analysis import av_backend
from ..audio_analysis.analyzer import (
    album_gain_peak_from_results,
    analyze_album_loudness,
    analyze_file,
)
from ..audio_analysis.cache import (
    AudioAnalysisCache,
)
from ..audio_analysis.models import (
    AudioAnalysisResult,
    FFmpegInstallation,
)
from ..audio_analysis.replaygain import (
    write_replaygain_tags,
)
from ..audio_analysis.spectrogram import (
    REFERENCE_RATE,
    SpectrogramError,
    render_spectrogram,
)
from ..i18n import tr
from ..models.song import Song
from ..settings import load_settings, save_settings


NORMAL_BACKGROUND = QColor(
    214,
    245,
    222,
)
ELEVATED_BACKGROUND = QColor(
    255,
    239,
    184,
)
CRITICAL_BACKGROUND = QColor(
    255,
    205,
    210,
)
ERROR_BACKGROUND = QColor(
    255,
    205,
    210,
)
STATUS_FOREGROUND = QColor(35, 42, 38)


class AnalysisWorker(QObject):
    progress = Signal(
        int,
        int,
        str,
    )
    result_ready = Signal(object)
    album_result_ready = Signal(
        object,
        object,
        object,
    )
    log_message = Signal(str)
    summary_ready = Signal(
        int,
        int,
        float,
    )
    finished = Signal()
    failed = Signal(str)

    def __init__(
        self,
        songs: list[Song],
        installation: FFmpegInstallation,
        calculate_album_gain: bool,
        max_workers: int,
        force_refresh: bool,
        language: str = "automatic",
        exact_album_gain: bool = False,
    ):
        super().__init__()

        self.language = language
        self.songs = songs
        self.installation = installation
        self.calculate_album_gain = (
            calculate_album_gain
        )
        self.exact_album_gain = exact_album_gain
        self.max_workers = max(
            1,
            max_workers,
        )
        self.force_refresh = force_refresh
        self.cancel_event = Event()
        self.cache = AudioAnalysisCache()

    @Slot()
    def run(self):
        started_at = time.perf_counter()
        cache_count = 0
        newly_analyzed_count = 0

        try:
            total = len(self.songs)
            completed_count = 0
            results_by_path: dict[
                str,
                AudioAnalysisResult,
            ] = {}

            self.log_message.emit(
                tr("log_started", self.language, workers=self.max_workers)
            )

            uncached_songs: list[Song] = []

            for song in self.songs:
                if self.cancel_event.is_set():
                    break

                cached = (
                    None
                    if self.force_refresh
                    else self.cache.get(
                        song.path
                    )
                )

                if cached is None:
                    uncached_songs.append(song)
                    continue

                results_by_path[
                    song.path
                ] = cached
                cache_count += 1
                completed_count += 1

                self.result_ready.emit(cached)
                self.progress.emit(
                    completed_count,
                    total,
                    tr(
                        "log_from_cache_progress",
                        self.language,
                        name=Path(song.path).name,
                    ),
                )
                self.log_message.emit(
                    tr("log_from_cache", self.language, name=Path(song.path).name)
                )

            if (
                uncached_songs
                and not self.cancel_event.is_set()
            ):
                with ThreadPoolExecutor(
                    max_workers=self.max_workers
                ) as executor:
                    futures = {
                        executor.submit(
                            analyze_file,
                            song.path,
                        ): song
                        for song in uncached_songs
                    }

                    for future in as_completed(
                        futures
                    ):
                        if self.cancel_event.is_set():
                            for pending in futures:
                                pending.cancel()
                            break

                        song = futures[future]

                        try:
                            result = future.result()
                        except Exception as error:
                            result = AudioAnalysisResult(
                                path=song.path,
                                error=str(error),
                            )

                        results_by_path[
                            song.path
                        ] = result
                        newly_analyzed_count += 1
                        completed_count += 1

                        if not result.error:
                            self.cache.put(result)

                            if result.peak_status == "critical":
                                marker = "✗"
                                detail = tr(
                                    "peak_critical_log",
                                    self.language,
                                    value=f"{result.true_peak_db:.2f}",
                                )
                            elif result.peak_status == "elevated":
                                marker = "⚠"
                                detail = tr(
                                    "peak_elevated_log",
                                    self.language,
                                    value=f"{result.true_peak_db:.2f}",
                                )
                            else:
                                marker = "✓"
                                detail = tr("peak_unremarkable", self.language)

                            self.log_message.emit(
                                (
                                    f"{marker} "
                                    f"{Path(song.path).name}\n"
                                    f"  {detail}"
                                )
                            )
                        else:
                            self.log_message.emit(
                                (
                                    "✗ "
                                    f"{Path(song.path).name}\n"
                                    f"  {result.error}"
                                )
                            )

                        self.result_ready.emit(result)
                        self.progress.emit(
                            completed_count,
                            total,
                            Path(song.path).name,
                        )

            if (
                not self.cancel_event.is_set()
                and self.calculate_album_gain
            ):
                grouped: dict[
                    tuple[str, str],
                    list[Song],
                ] = defaultdict(list)

                for song in self.songs:
                    key = (
                        (
                            song.album_artist
                            or song.artist
                        ),
                        song.album,
                    )
                    grouped[key].append(song)

                for key, album_songs in (
                    grouped.items()
                ):
                    if self.cancel_event.is_set():
                        break

                    cached_album_values = [
                        results_by_path.get(
                            song.path
                        )
                        for song in album_songs
                    ]
                    album_gain_is_cached = (
                        bool(cached_album_values)
                        and all(
                            result is not None
                            and (
                                result.replaygain_album_gain_db
                                is not None
                            )
                            for result in cached_album_values
                        )
                    )

                    if (
                        album_gain_is_cached
                        and not self.force_refresh
                    ):
                        first_result = (
                            cached_album_values[0]
                        )
                        self.album_result_ready.emit(
                            key,
                            (
                                first_result
                                .replaygain_album_gain_db
                            ),
                            (
                                first_result
                                .replaygain_album_peak
                            ),
                        )
                        self.log_message.emit(
                            tr(
                                "log_album_rg_cache",
                                self.language,
                                artist=key[0],
                                album=key[1],
                            )
                        )
                        continue

                    self.progress.emit(
                        completed_count,
                        total,
                        tr(
                            "progress_album_rg",
                            self.language,
                            artist=key[0],
                            album=key[1],
                        ),
                    )
                    self.log_message.emit(
                        tr(
                            "log_album_rg_calc",
                            self.language,
                            artist=key[0],
                            album=key[1],
                        )
                    )

                    if self.exact_album_gain:
                        # Exakt: ganzes Album am Stück dekodieren (langsamer).
                        gain, peak = analyze_album_loudness(
                            [song.path for song in album_songs]
                        )
                    else:
                        # Schnell: aus den Track-Werten ableiten (kein Decode).
                        gain, peak = album_gain_peak_from_results(
                            [
                                results_by_path[song.path]
                                for song in album_songs
                                if song.path in results_by_path
                            ]
                        )
                    self.album_result_ready.emit(
                        key,
                        gain,
                        peak,
                    )

            elapsed_seconds = (
                time.perf_counter()
                - started_at
            )
            self.summary_ready.emit(
                cache_count,
                newly_analyzed_count,
                elapsed_seconds,
            )
            self.progress.emit(
                total,
                total,
                (
                    tr("analysis_cancelled_progress", self.language)
                    if self.cancel_event.is_set()
                    else tr("analysis_done_progress", self.language)
                ),
            )
            self.finished.emit()
        except Exception as error:
            self.failed.emit(
                str(error)
            )

    @Slot()
    def cancel(self):
        self.cancel_event.set()


class _SpectrogramSignals(QObject):
    finished = Signal(str, str)
    failed = Signal(str, str)


class _SpectrogramTask(QRunnable):
    def __init__(
        self,
        source_path: str,
        installation: FFmpegInstallation,
        width: int,
        height: int,
        channel: int | None = None,
    ):
        super().__init__()
        self.signals = _SpectrogramSignals()
        self._source_path = source_path
        self._installation = installation
        self._width = width
        self._height = height
        self._channel = channel

    @Slot()
    def run(self):
        try:
            image_path = render_spectrogram(
                self._source_path,
                width=self._width,
                height=self._height,
                channel=self._channel,
            )
        except SpectrogramError as error:
            self.signals.failed.emit(
                self._source_path,
                str(error),
            )
            return

        self.signals.finished.emit(
            self._source_path,
            str(image_path),
        )


class AudioAnalysisDialog(QDialog):
    def __init__(
        self,
        selected_songs: list[Song],
        all_songs: list[Song],
        parent=None,
        *,
        embedded: bool = False,
        language: str = "automatic",
    ):
        super().__init__(parent)

        self.language = language
        self.embedded = embedded
        self.selected_songs = selected_songs
        self.all_songs = all_songs
        self.current_songs: list[Song] = []
        self.results: dict[
            str,
            AudioAnalysisResult,
        ] = {}
        self.thread: QThread | None = None
        self.worker: AnalysisWorker | None = None

        self._ordered_result_paths: list[str] = []
        self._spectrogram_source: str | None = None
        self._spectrogram_shown_source: str | None = None
        self._spec_channel: int | None = None
        self._spec_shown_channel: int | None = None
        self._spec_channel_buttons: list[QPushButton] = []
        self._spectrogram_pixmap: QPixmap | None = None
        self._spectrogram_pool = QThreadPool(self)
        self._spectrogram_pool.setMaxThreadCount(1)

        # Audio-Analyse läuft über PyAV (gebündeltes FFmpeg) – keine externe
        # ffmpeg.exe mehr. Der Installation-Shim hält die vorhandenen
        # .available/.version-Prüfungen der UI kompatibel.
        if av_backend.is_available():
            self.installation = FFmpegInstallation(
                ffmpeg_path="PyAV",
                ffprobe_path="PyAV",
                version=av_backend.ffmpeg_version(),
            )
        else:
            self.installation = FFmpegInstallation(
                ffmpeg_path="", ffprobe_path="", version=""
            )
        settings = load_settings()
        self.max_workers = (
            settings.audio_analysis_parallel_jobs
            or automatic_worker_count()
        )

        if not self.embedded:
            self.setWindowTitle(
                tr("audio_analysis", language)
            )
            self.resize(
                1500,
                840,
            )
        else:
            self.setWindowFlags(
                Qt.WindowType.Widget
            )

        layout = QVBoxLayout(self)

        if self.installation.available:
            status_text = tr(
                "ffmpeg_found",
                language,
                version=self.installation.version,
                path=self.installation.ffmpeg_path,
                workers=self.max_workers,
            )
        else:
            status_text = tr("ffmpeg_missing_long", language)

        self.status_label = QLabel(
            status_text
        )
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(
            self.status_label
        )

        self.statistics_label = QLabel(
            tr("analysis_not_run", language)
        )
        self.statistics_label.setWordWrap(True)
        layout.addWidget(
            self.statistics_label
        )

        self.album_gain_checkbox = QCheckBox(
            tr("album_rg_together", language)
        )
        self.album_gain_checkbox.setChecked(
            True
        )
        self.album_gain_checkbox.setToolTip(
            tr("album_rg_tip", language)
        )
        layout.addWidget(
            self.album_gain_checkbox
        )

        self.force_refresh_checkbox = QCheckBox(
            tr("ignore_cache", language)
        )
        self.force_refresh_checkbox.setChecked(
            False
        )
        self.force_refresh_checkbox.setToolTip(
            tr("ignore_cache_tip", language)
        )
        layout.addWidget(
            self.force_refresh_checkbox
        )

        button_widget = QWidget()
        button_layout = QVBoxLayout(
            button_widget
        )

        self.selected_button = QPushButton(
            tr("analyze_selected", language, count=len(selected_songs))
        )
        self.selected_button.clicked.connect(
            lambda:
            self.start_analysis(
                self.selected_songs
            )
        )

        self.all_button = QPushButton(
            tr("analyze_all", language, count=len(all_songs))
        )
        self.all_button.clicked.connect(
            lambda:
            self.start_analysis(
                self.all_songs
            )
        )

        self.cancel_button = QPushButton(
            tr("cancel_analysis_btn", language)
        )
        self.cancel_button.clicked.connect(
            self.cancel_analysis
        )
        self.cancel_button.setEnabled(False)

        button_layout.addWidget(
            self.selected_button
        )
        button_layout.addWidget(
            self.all_button
        )
        button_layout.addWidget(
            self.cancel_button
        )
        layout.addWidget(
            button_widget
        )

        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setValue(0)
        layout.addWidget(
            self.progress
        )

        self.tabs = QTabWidget()
        self.track_table = (
            self._create_track_table()
        )
        self.album_table = (
            self._create_album_table()
        )
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.details_tab = self._create_details_tab()
        self.spectrogram_tab = self._create_spectrogram_tab()

        self.tabs.addTab(
            self.track_table,
            tr("tab_track_analysis", language),
        )
        self.tabs.addTab(
            self.album_table,
            tr("tab_album_compare", language),
        )
        self.tabs.addTab(
            self.details_tab,
            tr("tab_details", language),
        )
        self.tabs.addTab(
            self.spectrogram_tab,
            tr("tab_spectrogram", language),
        )
        self.tabs.addTab(
            self.log_output,
            tr("tab_log", language),
        )
        layout.addWidget(
            self.tabs
        )

        self.track_table.itemSelectionChanged.connect(
            self._on_track_selection_changed
        )
        self.tabs.currentChanged.connect(
            self._on_tab_changed
        )

        self.write_button = QPushButton(
            tr("write_rg_tags", language)
        )
        self.write_button.clicked.connect(
            self.write_replaygain
        )
        self.write_button.setEnabled(False)

        self.close_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        close_buttons = self.close_buttons
        close_buttons.rejected.connect(
            self.reject
        )
        close_buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText(
            tr("close_btn", language)
        )

        layout.addWidget(
            self.write_button
        )
        layout.addWidget(
            close_buttons
        )

        if self.embedded:
            close_buttons.hide()

        enabled = (
            self.installation.available
            and bool(all_songs)
        )
        self.selected_button.setEnabled(
            enabled
            and bool(selected_songs)
        )
        self.all_button.setEnabled(
            enabled
        )

    def _create_track_table(
        self,
    ) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(16)
        lang = self.language
        table.setHorizontalHeaderLabels(
            [
                tr("col_file", lang),
                tr("col_codec", lang),
                tr("col_rate", lang),
                tr("col_bit", lang),
                tr("col_channels", lang),
                tr("col_bitrate", lang),
                tr("col_duration", lang),
                tr("col_lufs", lang),
                tr("col_lra", lang),
                tr("col_true_peak", lang),
                tr("col_peak_note", lang),
                tr("col_track_gain", lang),
                tr("col_track_peak", lang),
                tr("col_album_gain", lang),
                tr("col_album_peak", lang),
                tr("col_source", lang),
            ]
        )
        true_peak_header = table.horizontalHeaderItem(9)
        if true_peak_header is not None:
            true_peak_header.setToolTip(
                tr("true_peak_tip", lang)
            )
        peak_status_header = table.horizontalHeaderItem(10)
        if peak_status_header is not None:
            peak_status_header.setToolTip(
                tr("peak_status_tip", lang)
            )
        track_peak_header = table.horizontalHeaderItem(12)
        if track_peak_header is not None:
            track_peak_header.setToolTip(
                tr("track_peak_tip", lang)
            )
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        table.setAlternatingRowColors(
            True
        )

        header = table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        # Spalten per Drag & Drop umsortierbar – Reihenfolge wird gespeichert.
        header.setSectionsMovable(True)

        for column in range(1, 16):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        # Erst gespeicherten Zustand wiederherstellen, DANN das Speichern
        # verbinden – restoreState kann sonst sofort ein Speichern auslösen.
        self._restore_column_state(header)
        header.sectionMoved.connect(self._persist_column_state)
        return table

    def _restore_column_state(self, header) -> None:
        state = load_settings().audio_analysis_column_state
        if not state:
            return
        try:
            header.restoreState(QByteArray.fromBase64(state.encode("ascii")))
        except Exception:
            pass  # Beschädigter/veralteter Zustand -> Standardreihenfolge

    def _persist_column_state(self, *_args) -> None:
        from dataclasses import replace

        header = self.track_table.horizontalHeader()
        state = bytes(header.saveState().toBase64()).decode("ascii")
        try:
            save_settings(replace(load_settings(), audio_analysis_column_state=state))
        except Exception:
            pass

    def _create_album_table(
        self,
    ) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(11)
        lang = self.language
        table.setHorizontalHeaderLabels(
            [
                tr("col_album", lang),
                tr("col_title", lang),
                tr("col_majority", lang),
                tr("col_avg_bitrate", lang),
                tr("col_avg_lufs", lang),
                tr("col_album_gain", lang),
                tr("col_album_peak", lang),
                tr("col_tech_outliers", lang),
                tr("col_peak_notes", lang),
                tr("col_not_analyzed", lang),
                tr("col_health", lang),
            ]
        )
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        table.setAlternatingRowColors(
            True
        )

        header = table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionsMovable(True)

        for column in range(1, 11):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        return table

    def _create_details_tab(self) -> QWidget:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        self.details_view = QLabel()
        self.details_view.setTextFormat(Qt.TextFormat.RichText)
        self.details_view.setWordWrap(True)
        self.details_view.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.details_view.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.details_view.setContentsMargins(16, 16, 16, 16)
        self.details_view.setText(
            f"<i>{tr('detail_hint', self.language)}</i>"
        )

        scroll_area.setWidget(self.details_view)
        return scroll_area

    def _refresh_details_for_selection(self) -> None:
        path = self._selected_result_path()
        result = self.results.get(path) if path is not None else None

        if result is None or result.error:
            self.details_view.setText(
                f"<i>{tr('detail_hint', self.language)}</i>"
            )
            return

        self.details_view.setText(
            _details_html(result, self.language)
        )

    def _create_spectrogram_tab(self) -> QWidget:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        self.spectrogram_status = QLabel(
            tr("spectrogram_hint", self.language)
        )
        self.spectrogram_status.setWordWrap(True)
        container_layout.addWidget(
            self.spectrogram_status
        )

        # Kanal-Umschalter (Alle / Ch 1 / Ch 2 …) – wird je nach gewähltem
        # Titel dynamisch neu aufgebaut.
        self.spectrogram_channel_bar = QWidget()
        self._spec_channel_layout = QHBoxLayout(self.spectrogram_channel_bar)
        self._spec_channel_layout.setContentsMargins(0, 0, 0, 0)
        self._spec_channel_layout.addStretch(1)
        container_layout.addWidget(self.spectrogram_channel_bar)

        self.spectrogram_view = QLabel()
        self.spectrogram_view.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.spectrogram_view.setStyleSheet(
            "background: #000000;"
        )
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(
            self.spectrogram_view
        )
        container_layout.addWidget(
            scroll_area
        )

        self.spectrogram_footer = QLabel("")
        self.spectrogram_footer.setStyleSheet("color:#5a6b60;")
        container_layout.addWidget(self.spectrogram_footer)

        return container

    def _rebuild_channel_bar(self, result: AudioAnalysisResult | None) -> None:
        """Baut die Kanal-Buttons passend zum gewählten Titel neu auf."""
        for button in self._spec_channel_buttons:
            self._spec_channel_layout.removeWidget(button)
            button.deleteLater()
        self._spec_channel_buttons = []

        channel_count = result.channel_count if result is not None else 0
        if channel_count <= 1:
            self.spectrogram_channel_bar.setVisible(False)
            self._spec_channel = None
            return

        self.spectrogram_channel_bar.setVisible(True)
        labels = [(tr("spec_channel_all", self.language), None)]
        for index in range(channel_count):
            labels.append((f"Ch {index + 1}", index))

        for text, channel in labels:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setChecked(channel == self._spec_channel)
            button.clicked.connect(
                lambda _checked=False, ch=channel: self._select_spec_channel(ch)
            )
            self._spec_channel_layout.insertWidget(
                self._spec_channel_layout.count() - 1, button
            )
            self._spec_channel_buttons.append(button)

    def _select_spec_channel(self, channel: int | None) -> None:
        self._spec_channel = channel
        for button in self._spec_channel_buttons:
            button.setChecked(button.text() == self._channel_button_text(channel))
        self._request_spectrogram_for_selection()

    def _channel_button_text(self, channel: int | None) -> str:
        if channel is None:
            return tr("spec_channel_all", self.language)
        return f"Ch {channel + 1}"

    def _on_tab_changed(self, _index: int) -> None:
        current = self.tabs.currentWidget()
        if current is self.spectrogram_tab:
            self._ensure_selection()
            self._request_spectrogram_for_selection()
        elif current is self.details_tab:
            self._ensure_selection()
            self._refresh_details_for_selection()

    def _on_track_selection_changed(self) -> None:
        current = self.tabs.currentWidget()
        if current is self.spectrogram_tab:
            self._request_spectrogram_for_selection()
        elif current is self.details_tab:
            self._refresh_details_for_selection()

    def _ensure_selection(self) -> None:
        """Ohne Auswahl den ersten Titel markieren – Details/Spektrogramm
        hängen an der Tabellen-Auswahl, die auf anderen Reitern unsichtbar ist.
        """
        rows = self.track_table.selectionModel()
        if (
            self.track_table.rowCount() > 0
            and (rows is None or not rows.hasSelection())
        ):
            self.track_table.selectRow(0)

    def _selected_result_path(self) -> str | None:
        rows = self.track_table.selectionModel()

        if rows is None or not rows.hasSelection():
            return None

        row = self.track_table.currentRow()

        if 0 <= row < len(self._ordered_result_paths):
            return self._ordered_result_paths[row]

        return None

    def _request_spectrogram_for_selection(self) -> None:
        path = self._selected_result_path()
        result = self.results.get(path) if path is not None else None

        if path is None:
            self._spectrogram_source = None
            self._spectrogram_shown_source = None
            self._rebuild_channel_bar(None)
            self.spectrogram_footer.setText("")
            self.spectrogram_view.clear()
            self.spectrogram_status.setText(
                tr("spectrogram_hint", self.language)
            )
            return

        self._rebuild_channel_bar(result)
        if result is not None and result.sample_rate:
            # Achsen-Obergrenze = feste Referenz (96 kHz), bei höher aufgelöstem
            # Material die echte Nyquist-Grenze der Datei.
            ceiling_hz = max(REFERENCE_RATE, result.sample_rate) / 2.0
            self.spectrogram_footer.setText(
                tr(
                    "spec_footer",
                    self.language,
                    rate=result.sample_rate,
                    nyquist=result.nyquist_text,
                    ceiling=f"{ceiling_hz / 1000:.0f} kHz",
                )
            )
        else:
            self.spectrogram_footer.setText("")

        if not self.installation.available:
            self.spectrogram_status.setText(
                tr("spectrogram_ffmpeg_missing", self.language)
            )
            return

        if (
            path == self._spectrogram_shown_source
            and self._spec_channel == self._spec_shown_channel
        ):
            return

        self._spectrogram_source = path
        self.spectrogram_status.setText(
            tr("spectrogram_creating", self.language, name=Path(path).name)
        )

        task = _SpectrogramTask(
            path,
            self.installation,
            960,
            480,
            self._spec_channel,
        )
        task.signals.finished.connect(
            self._on_spectrogram_ready
        )
        task.signals.failed.connect(
            self._on_spectrogram_failed
        )
        self._spectrogram_pool.start(task)

    @Slot(str, str)
    def _on_spectrogram_ready(
        self,
        source_path: str,
        image_path: str,
    ) -> None:
        if source_path != self._spectrogram_source:
            return

        pixmap = QPixmap(image_path)

        if pixmap.isNull():
            self.spectrogram_status.setText(
                tr("spectrogram_load_failed", self.language)
            )
            return

        self._spectrogram_pixmap = pixmap
        self._spectrogram_shown_source = source_path
        self._spec_shown_channel = self._spec_channel
        self.spectrogram_view.setPixmap(pixmap)
        self.spectrogram_view.setMinimumSize(
            pixmap.size()
        )
        self.spectrogram_status.setText(
            tr("spectrogram_ready", self.language, name=Path(source_path).name)
        )

    @Slot(str, str)
    def _on_spectrogram_failed(
        self,
        source_path: str,
        message: str,
    ) -> None:
        if source_path != self._spectrogram_source:
            return

        self.spectrogram_view.clear()
        self.spectrogram_status.setText(
            tr("spectrogram_failed", self.language, message=message)
        )

    def set_songs(
        self,
        selected_songs: list[Song],
        all_songs: list[Song],
    ) -> None:
        self.selected_songs = list(selected_songs)
        self.all_songs = list(all_songs)
        running = self._thread_is_running()
        self.selected_button.setText(
            tr("analyze_selected", self.language, count=len(self.selected_songs))
        )
        self.selected_button.setEnabled(
            bool(self.selected_songs)
            and self.installation.available
            and not running
        )
        self.all_button.setText(
            tr("analyze_all", self.language, count=len(self.all_songs))
        )
        self.all_button.setEnabled(
            bool(self.all_songs)
            and self.installation.available
            and not running
        )

    def start_analysis(
        self,
        songs: list[Song],
    ):
        if not songs:
            return

        if not self.installation.available:
            QMessageBox.warning(
                self,
                tr("ffmpeg_missing_title", self.language),
                tr("ffmpeg_missing_short", self.language),
            )
            return

        self.current_songs = list(songs)
        self.results.clear()
        self.track_table.setRowCount(0)
        self.album_table.setRowCount(0)
        self.log_output.clear()
        self.statistics_label.setText(
            tr("analysis_running", self.language)
        )
        self.progress.setMaximum(
            len(songs)
        )
        self.progress.setValue(0)
        self.write_button.setEnabled(False)

        self.selected_button.setEnabled(False)
        self.all_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        self.thread = QThread(self)
        self.worker = AnalysisWorker(
            songs,
            self.installation,
            self.album_gain_checkbox.isChecked(),
            self.max_workers,
            self.force_refresh_checkbox.isChecked(),
            self.language,
            exact_album_gain=load_settings().audio_analysis_exact_album_gain,
        )
        self.worker.moveToThread(
            self.thread
        )

        self.thread.started.connect(
            self.worker.run
        )
        self.worker.progress.connect(
            self.update_progress
        )
        self.worker.result_ready.connect(
            self.receive_result
        )
        self.worker.album_result_ready.connect(
            self.receive_album_result
        )
        self.worker.log_message.connect(
            self.append_log
        )
        self.worker.summary_ready.connect(
            self.receive_summary
        )
        self.worker.finished.connect(
            self.analysis_finished
        )
        self.worker.failed.connect(
            self.analysis_failed
        )
        self.worker.finished.connect(
            self.thread.quit
        )
        self.worker.failed.connect(
            self.thread.quit
        )
        current_thread = self.thread
        current_thread.finished.connect(
            current_thread.deleteLater
        )
        current_thread.finished.connect(
            lambda thread=current_thread:
            self._clear_finished_thread(thread)
        )

        current_thread.start()

    def cancel_analysis(self):
        if self.worker is not None:
            self.worker.cancel()
            self.status_label.setText(
                tr("analysis_cancelling", self.language)
            )

    def update_progress(
        self,
        value: int,
        maximum: int,
        text: str,
    ):
        self.progress.setMaximum(
            max(1, maximum)
        )
        self.progress.setValue(value)
        self.status_label.setText(
            text
        )

    def append_log(
        self,
        text: str,
    ):
        if self.log_output.toPlainText():
            self.log_output.appendPlainText("")

        self.log_output.appendPlainText(
            text
        )

    def receive_summary(
        self,
        cache_count: int,
        newly_analyzed_count: int,
        elapsed_seconds: float,
    ):
        total_count = (
            cache_count
            + newly_analyzed_count
        )
        average_seconds = (
            elapsed_seconds / total_count
            if total_count
            else 0.0
        )

        self.statistics_label.setText(
            tr(
                "analysis_summary_stat",
                self.language,
                total=total_count,
                cache=cache_count,
                newly=newly_analyzed_count,
                seconds=f"{elapsed_seconds:.2f}",
                avg=f"{average_seconds:.2f}",
            )
        )
        self.append_log(
            tr(
                "analysis_summary_log",
                self.language,
                total=total_count,
                cache=cache_count,
                newly=newly_analyzed_count,
                seconds=f"{elapsed_seconds:.2f}",
            )
        )

    def receive_result(
        self,
        result: AudioAnalysisResult,
    ):
        self.results[
            result.path
        ] = result
        self._refresh_track_table()
        self._refresh_album_table()

        if self.tabs.currentWidget() is self.details_tab:
            self._refresh_details_for_selection()

    def receive_album_result(
        self,
        album_key,
        gain,
        peak,
    ):
        album_songs = [
            song
            for song in self.current_songs
            if (
                (
                    (
                        song.album_artist
                        or song.artist
                    ),
                    song.album,
                )
                == tuple(album_key)
            )
        ]

        cache = AudioAnalysisCache()

        for song in album_songs:
            result = self.results.get(
                song.path
            )

            if result is None:
                continue

            updated = (
                result.with_album_replaygain(
                    gain,
                    peak,
                )
            )
            self.results[
                song.path
            ] = updated
            cache.put(updated)

        self._refresh_track_table()
        self._refresh_album_table()

    def analysis_finished(self):
        self.cancel_button.setEnabled(False)
        self.selected_button.setEnabled(
            bool(self.selected_songs)
        )
        self.all_button.setEnabled(
            bool(self.all_songs)
        )
        self.write_button.setEnabled(
            any(
                not result.error
                and (
                    result.replaygain_track_gain_db
                    is not None
                )
                for result in self.results.values()
            )
        )
        self.status_label.setText(
            tr("analysis_finished_status", self.language, count=len(self.results))
        )
        self._refresh_track_table()
        self._refresh_album_table()

    def analysis_failed(
        self,
        message: str,
    ):
        self.cancel_button.setEnabled(False)
        self.selected_button.setEnabled(
            bool(self.selected_songs)
        )
        self.all_button.setEnabled(
            bool(self.all_songs)
        )
        QMessageBox.critical(
            self,
            tr("analysis_failed_title", self.language),
            message,
        )

    def _refresh_track_table(self):
        ordered_results = [
            self.results[song.path]
            for song in self.current_songs
            if song.path in self.results
        ]
        self._ordered_result_paths = [
            result.path
            for result in ordered_results
        ]
        self.track_table.setRowCount(
            len(ordered_results)
        )

        for row, result in enumerate(
            ordered_results
        ):
            values = [
                result.filename,
                result.codec.upper(),
                result.sample_rate_text,
                (
                    str(result.bit_depth)
                    if result.bit_depth
                    else ""
                ),
                (
                    result.channel_layout
                    or str(result.channels)
                ),
                result.bitrate_text,
                result.duration_text,
                _format_number(
                    result.integrated_lufs,
                    " LUFS",
                ),
                _format_number(
                    result.loudness_range_lu,
                    " LU",
                ),
                _format_number(
                    result.true_peak_db,
                    " dBTP",
                ),
                peak_status_label(
                    result.peak_status,
                    self.language,
                ),
                _format_gain(
                    result.replaygain_track_gain_db
                ),
                _format_peak(
                    result.replaygain_track_peak
                ),
                _format_gain(
                    result.replaygain_album_gain_db
                ),
                _format_peak(
                    result.replaygain_album_peak
                ),
                (
                    tr("source_cache", self.language)
                    if result.from_cache
                    else tr("source_new", self.language)
                ),
            ]

            if result.error:
                values[1] = tr("error_short", self.language)
                values[7] = result.error

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    value
                )

                if result.error:
                    item.setBackground(
                        ERROR_BACKGROUND
                    )
                    item.setForeground(
                        STATUS_FOREGROUND
                    )
                elif column in {
                    9,
                    10,
                }:
                    color = peak_status_color(
                        result.peak_status
                    )

                    if color is not None:
                        item.setBackground(
                            color
                        )
                        item.setForeground(
                            STATUS_FOREGROUND
                        )

                self.track_table.setItem(
                    row,
                    column,
                    item,
                )

    def _refresh_album_table(self):
        summaries = group_results_by_album(
            self.current_songs,
            self.results,
        )
        self.album_table.setRowCount(
            len(summaries)
        )

        for row, summary in enumerate(
            summaries
        ):
            values = [
                summary.display_name,
                str(summary.track_count),
                signature_text(
                    summary.dominant_signature
                ),
                (
                    f"{summary.average_bitrate / 1000:.0f} kbit/s"
                    if (
                        summary.average_bitrate
                        is not None
                    )
                    else ""
                ),
                (
                    f"{summary.average_lufs:.2f} LUFS"
                    if summary.average_lufs
                    is not None
                    else ""
                ),
                _format_gain(
                    summary.album_gain_db
                ),
                _format_peak(
                    summary.album_peak
                ),
                str(
                    len(
                        summary.technical_outliers
                    )
                ),
                str(
                    summary.peak_warning_count
                ),
                str(
                    len(
                        summary.missing_analysis_files
                    )
                ),
                f"{summary.health_score} / 100",
            ]

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    value
                )

                if column == 10:
                    item.setBackground(
                        health_score_color(
                            summary.health_score
                        )
                    )
                    item.setForeground(
                        STATUS_FOREGROUND
                    )
                elif (
                    summary.has_warnings
                    and column in {
                        7,
                        8,
                        9,
                    }
                ):
                    item.setBackground(
                        ELEVATED_BACKGROUND
                    )
                    item.setForeground(
                        STATUS_FOREGROUND
                    )

                tooltip_lines: list[str] = []

                if summary.technical_outliers:
                    tooltip_lines.append(
                        tr(
                            "tech_outliers_tip",
                            self.language,
                            items="\n".join(summary.technical_outliers),
                        )
                    )

                if summary.elevated_peak_files:
                    tooltip_lines.append(
                        tr(
                            "peak_1_2_tip",
                            self.language,
                            items="\n".join(summary.elevated_peak_files),
                        )
                    )

                if summary.critical_peak_files:
                    tooltip_lines.append(
                        tr(
                            "peak_over_2_tip",
                            self.language,
                            items="\n".join(summary.critical_peak_files),
                        )
                    )

                if summary.missing_analysis_files:
                    tooltip_lines.append(
                        tr(
                            "not_analyzed_tip",
                            self.language,
                            items="\n".join(summary.missing_analysis_files),
                        )
                    )

                if tooltip_lines:
                    item.setToolTip(
                        "\n\n".join(
                            tooltip_lines
                        )
                    )

                self.album_table.setItem(
                    row,
                    column,
                    item,
                )

    def write_replaygain(self):
        valid_results = [
            result
            for result in self.results.values()
            if (
                not result.error
                and (
                    result.replaygain_track_gain_db
                    is not None
                )
            )
        ]

        if not valid_results:
            return

        answer = QMessageBox.question(
            self,
            tr("write_rg_title", self.language),
            tr("write_rg_question", self.language, count=len(valid_results)),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            == QMessageBox.StandardButton.Cancel
        ):
            return

        overwrite = (
            answer
            == QMessageBox.StandardButton.Yes
        )

        progress_dialog = QProgressDialog(
            tr("writing_rg", self.language),
            tr("cancel", self.language),
            0,
            len(valid_results),
            self,
        )
        progress_dialog.setWindowTitle(
            tr("write_rg_title", self.language)
        )
        progress_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setValue(0)

        saved = 0
        failures: list[str] = []

        for index, result in enumerate(
            valid_results,
            start=1,
        ):
            if progress_dialog.wasCanceled():
                break

            progress_dialog.setLabelText(
                tr(
                    "writing_rg_label",
                    self.language,
                    filename=result.filename,
                    index=index,
                    total=len(valid_results),
                )
            )
            QApplication.processEvents()

            try:
                write_replaygain_tags(
                    result,
                    overwrite=overwrite,
                )
            except Exception as error:
                failures.append(
                    f"{result.filename}: {error}"
                )
            else:
                saved += 1

            progress_dialog.setValue(index)
            QApplication.processEvents()

        progress_dialog.close()

        message = tr("rg_written", self.language, count=saved)

        if progress_dialog.wasCanceled():
            message += tr("rg_cancelled", self.language)

        if failures:
            message += tr(
                "errors_block",
                self.language,
                errors="\n".join(failures),
            )

        QMessageBox.information(
            self,
            tr("rg_done_title", self.language),
            message,
        )

    def _clear_finished_thread(
        self,
        finished_thread: QThread,
    ) -> None:
        if self.thread is finished_thread:
            self.thread = None

    def _thread_is_running(
        self,
    ) -> bool:
        thread = self.thread

        if thread is None:
            return False

        try:
            return thread.isRunning()
        except RuntimeError:
            self.thread = None
            return False

    def closeEvent(self, event):
        if self._thread_is_running():
            answer = QMessageBox.question(
                self,
                tr("analysis_running_title", self.language),
                tr("analysis_running_close", self.language),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if (
                answer
                != QMessageBox.StandardButton.Yes
            ):
                event.ignore()
                return

            self.cancel_analysis()
            thread = self.thread

            if thread is not None:
                try:
                    thread.quit()
                    thread.wait(3000)
                except RuntimeError:
                    self.thread = None

        event.accept()


def automatic_worker_count() -> int:
    cpu_count = os.cpu_count() or 1

    if cpu_count >= 8:
        return 4

    if cpu_count >= 4:
        return 2

    return 1


def peak_status_label(
    status: str,
    language: str = "automatic",
) -> str:
    return {
        "normal": tr("peak_normal", language),
        "elevated": tr("peak_elevated", language),
        "critical": tr("peak_critical", language),
        "unknown": tr("peak_unknown", language),
    }.get(
        status,
        tr("peak_unknown", language),
    )


def peak_status_color(
    status: str,
) -> QColor | None:
    return {
        "normal": NORMAL_BACKGROUND,
        "elevated": ELEVATED_BACKGROUND,
        "critical": CRITICAL_BACKGROUND,
    }.get(status)


def health_score_color(
    score: int,
) -> QColor:
    if score >= 90:
        return NORMAL_BACKGROUND

    if score >= 70:
        return ELEVATED_BACKGROUND

    return CRITICAL_BACKGROUND


def _db(value: float | None, suffix: str = " dB") -> str:
    if value is None:
        return "–"
    return f"{value:.2f}{suffix}"


_AUTH_COLORS = {
    "genuine": ("#1b5e20", "#d6f5de"),
    "suspect": ("#7a5b00", "#ffefb8"),
    "fake": ("#8a1c1c", "#ffcdd2"),
    "lossy": ("#37474f", "#e3e7e9"),
    "unknown": ("#37474f", "#e3e7e9"),
}


def _authenticity_banner(result: AudioAnalysisResult, language: str) -> str:
    from ..audio_analysis.authenticity import assess

    verdict = assess(
        codec=result.codec,
        sample_rate=result.sample_rate,
        spectral_cutoff_hz=result.spectral_cutoff_hz,
        shelf_db=result.spectral_shelf_db,
        steepness_db=result.spectral_steepness_db,
    )
    cutoff = result.spectral_cutoff_text or "–"
    message = tr(verdict.message_key, language, cutoff=cutoff)
    # Konfidenz nur zeigen, wo eine Warnung fällt (nicht bei „unauffällig").
    if verdict.level in ("fake", "suspect"):
        confidence = tr(f"auth_conf_{verdict.confidence}", language)
        message += f" · {tr('auth_confidence', language)}: {confidence}"
    foreground, background = _AUTH_COLORS.get(verdict.level, _AUTH_COLORS["unknown"])
    label = tr("auth_label", language)
    return (
        f"<div style='background:{background}; color:{foreground}; "
        "padding:8px 12px; border-radius:6px; margin-bottom:12px;'>"
        f"<b>{label}:</b> {message}</div>"
    )


def _details_html(result: AudioAnalysisResult, language: str) -> str:
    """Rich-Text-Karte mit allen technischen Kennzahlen eines Titels."""

    def rows(pairs: list[tuple[str, str]]) -> str:
        cells = "".join(
            (
                "<tr>"
                f"<td style='padding:2px 18px 2px 0; color:#5a6b60;'>{label}</td>"
                f"<td style='padding:2px 0;'><b>{value or '–'}</b></td>"
                "</tr>"
            )
            for label, value in pairs
        )
        return f"<table cellspacing='0' cellpadding='0'>{cells}</table>"

    channels = result.channels or result.channel_layout
    technical = [
        (tr("detail_codec", language), (result.codec or "").upper()),
        (tr("detail_sample_rate", language), result.sample_rate_text),
        (
            tr("detail_bit_depth", language),
            f"{result.bit_depth}-bit" if result.bit_depth else "",
        ),
        (tr("detail_decoded_format", language), result.decoded_format),
        (tr("detail_bitrate", language), result.bitrate_text),
        (
            tr("detail_channels", language),
            result.channel_layout or (str(channels) if channels else ""),
        ),
        (tr("detail_length", language), result.duration_text),
        (tr("detail_nyquist", language), result.nyquist_text),
        (tr("detail_size", language), result.file_size_text),
    ]

    if result.clipped_samples > 0:
        clipping = tr("detail_clipping_count", language, count=result.clipped_samples)
    else:
        clipping = tr("detail_no_clipping", language)

    levels = [
        (tr("detail_dynamic_range", language), _db(result.dynamic_range_db)),
        (tr("detail_maximum", language), _db(result.peak_dbfs, " dBFS")),
        (tr("detail_rms", language), _db(result.rms_dbfs, " dBFS")),
        (tr("detail_lufs", language), _db(result.integrated_lufs, " LUFS")),
        (tr("detail_true_peak", language), _db(result.true_peak_db, " dBTP")),
        (tr("detail_clipping", language), clipping),
        (tr("detail_spectral_cutoff", language), result.spectral_cutoff_text),
        (tr("detail_samples", language), result.sample_count_text),
    ]

    channel_rows = []
    for index in range(result.channel_count):
        label = tr("detail_channel_label", language, index=index + 1)
        peak = _db(result.channel_peaks_dbfs[index], "")
        rms = _db(result.channel_rms_dbfs[index], "")
        dyn = _db(result.channel_dynamic_range_db[index], "")
        channel_rows.append((label, f"P {peak} / R {rms} / DR {dyn}"))

    section = (
        "<div style='margin-bottom:14px;'>"
        "<div style='font-weight:bold; color:#2f3a34; margin-bottom:4px;'>{title}</div>"
        "{body}</div>"
    )
    html = [
        f"<div style='font-size:14px; font-weight:bold; margin-bottom:10px;'>"
        f"{result.filename}</div>",
        _authenticity_banner(result, language),
        section.format(
            title=tr("detail_section_technical", language), body=rows(technical)
        ),
        section.format(
            title=tr("detail_section_levels", language), body=rows(levels)
        ),
    ]
    if channel_rows:
        html.append(
            section.format(
                title=tr("detail_section_channels", language),
                body=rows(channel_rows),
            )
        )
    return "".join(html)


def _format_number(
    value: float | None,
    suffix: str,
) -> str:
    if value is None:
        return ""

    return f"{value:.2f}{suffix}"


def _format_gain(
    value: float | None,
) -> str:
    if value is None:
        return ""

    return f"{value:+.2f} dB"


def _format_peak(
    value: float | None,
) -> str:
    if value is None:
        return ""

    return f"{value:.8f}"
