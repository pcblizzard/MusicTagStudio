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
    QObject,
    QThread,
    Signal,
    Slot,
    Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QProgressDialog,
    QPushButton,
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
from ..audio_analysis.analyzer import (
    analyze_album_loudness,
    analyze_file,
)
from ..audio_analysis.cache import (
    AudioAnalysisCache,
)
from ..audio_analysis.ffmpeg_tools import (
    find_ffmpeg,
)
from ..audio_analysis.models import (
    AudioAnalysisResult,
    FFmpegInstallation,
)
from ..audio_analysis.replaygain import (
    write_replaygain_tags,
)
from ..models.song import Song
from ..settings import load_settings


NORMAL_BACKGROUND = QColor(
    43,
    78,
    55,
)
ELEVATED_BACKGROUND = QColor(
    86,
    78,
    38,
)
CRITICAL_BACKGROUND = QColor(
    112,
    42,
    42,
)
ERROR_BACKGROUND = QColor(
    100,
    45,
    45,
)


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
    ):
        super().__init__()

        self.songs = songs
        self.installation = installation
        self.calculate_album_gain = (
            calculate_album_gain
        )
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
                (
                    "Analyse gestartet\n"
                    f"Parallele FFmpeg-Prozesse: "
                    f"{self.max_workers}\n"
                )
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
                    (
                        "Aus Cache geladen: "
                        f"{Path(song.path).name}"
                    ),
                )
                self.log_message.emit(
                    (
                        "✓ "
                        f"{Path(song.path).name}\n"
                        "  Aus Analyse-Cache geladen"
                    )
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
                            self.installation,
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
                                detail = (
                                    "Kritischer True Peak: "
                                    f"{result.true_peak_db:.2f} dBTP"
                                )
                            elif result.peak_status == "elevated":
                                marker = "⚠"
                                detail = (
                                    "Erhöhter True Peak: "
                                    f"{result.true_peak_db:.2f} dBTP"
                                )
                            else:
                                marker = "✓"
                                detail = "Unauffällig"

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
                            (
                                "✓ Album-ReplayGain aus Cache\n"
                                f"  {key[0]} – {key[1]}"
                            )
                        )
                        continue

                    self.progress.emit(
                        completed_count,
                        total,
                        (
                            "Album-ReplayGain: "
                            f"{key[0]} – {key[1]}"
                        ),
                    )
                    self.log_message.emit(
                        (
                            "• Berechne Album-ReplayGain\n"
                            f"  {key[0]} – {key[1]}"
                        )
                    )

                    gain, peak = (
                        analyze_album_loudness(
                            [
                                song.path
                                for song in album_songs
                            ],
                            self.installation,
                        )
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
                    "Analyse abgebrochen"
                    if self.cancel_event.is_set()
                    else "Analyse abgeschlossen"
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


class AudioAnalysisDialog(QDialog):
    def __init__(
        self,
        selected_songs: list[Song],
        all_songs: list[Song],
        parent=None,
    ):
        super().__init__(parent)

        self.selected_songs = selected_songs
        self.all_songs = all_songs
        self.current_songs: list[Song] = []
        self.results: dict[
            str,
            AudioAnalysisResult,
        ] = {}
        self.thread: QThread | None = None
        self.worker: AnalysisWorker | None = None

        self.installation = find_ffmpeg()
        settings = load_settings()
        self.max_workers = (
            settings.audio_analysis_parallel_jobs
            or automatic_worker_count()
        )

        self.setWindowTitle(
            "Audio-Analyse"
        )
        self.resize(
            1500,
            840,
        )

        layout = QVBoxLayout(self)

        if self.installation.available:
            status_text = (
                "FFmpeg gefunden: "
                f"{self.installation.version}\n"
                f"{self.installation.ffmpeg_path}\n"
                f"Parallele Analysen: "
                f"{self.max_workers}"
            )
        else:
            status_text = (
                "FFmpeg und ffprobe wurden nicht gefunden. "
                "Die Analyse ist erst nach der Einrichtung verfügbar."
            )

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
            "Noch keine Analyse durchgeführt."
        )
        self.statistics_label.setWordWrap(True)
        layout.addWidget(
            self.statistics_label
        )

        self.album_gain_checkbox = QCheckBox(
            "Album-ReplayGain gemeinsam berechnen"
        )
        self.album_gain_checkbox.setChecked(
            True
        )
        self.album_gain_checkbox.setToolTip(
            "Analysiert alle ausgewählten Titel eines Albums "
            "zusätzlich als zusammenhängendes Album."
        )
        layout.addWidget(
            self.album_gain_checkbox
        )

        self.force_refresh_checkbox = QCheckBox(
            "Analyse-Cache ignorieren und neu berechnen"
        )
        self.force_refresh_checkbox.setChecked(
            False
        )
        self.force_refresh_checkbox.setToolTip(
            "Unveränderte Dateien werden normalerweise aus dem "
            "lokalen Analyse-Cache geladen."
        )
        layout.addWidget(
            self.force_refresh_checkbox
        )

        button_widget = QWidget()
        button_layout = QVBoxLayout(
            button_widget
        )

        self.selected_button = QPushButton(
            (
                f"Markierte Titel analysieren "
                f"({len(selected_songs)})"
            )
        )
        self.selected_button.clicked.connect(
            lambda:
            self.start_analysis(
                self.selected_songs
            )
        )

        self.all_button = QPushButton(
            (
                f"Alle gescannten Titel analysieren "
                f"({len(all_songs)})"
            )
        )
        self.all_button.clicked.connect(
            lambda:
            self.start_analysis(
                self.all_songs
            )
        )

        self.cancel_button = QPushButton(
            "Analyse abbrechen"
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

        self.tabs.addTab(
            self.track_table,
            "Titelanalyse",
        )
        self.tabs.addTab(
            self.album_table,
            "Albumvergleich",
        )
        self.tabs.addTab(
            self.log_output,
            "Verlauf",
        )
        layout.addWidget(
            self.tabs
        )

        self.write_button = QPushButton(
            "ReplayGain-Tags schreiben"
        )
        self.write_button.clicked.connect(
            self.write_replaygain
        )
        self.write_button.setEnabled(False)

        close_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        close_buttons.rejected.connect(
            self.reject
        )
        close_buttons.button(
            QDialogButtonBox.StandardButton.Close
        ).setText(
            "Schließen"
        )

        layout.addWidget(
            self.write_button
        )
        layout.addWidget(
            close_buttons
        )

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
        table.setHorizontalHeaderLabels(
            [
                "Datei",
                "Codec",
                "Rate",
                "Bit",
                "Kanäle",
                "Bitrate",
                "Dauer",
                "LUFS",
                "LRA",
                "True Peak",
                "Peak-Hinweis",
                "Track Gain",
                "Track Peak",
                "Album Gain",
                "Album Peak",
                "Quelle",
            ]
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

        for column in range(1, 16):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        return table

    def _create_album_table(
        self,
    ) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(11)
        table.setHorizontalHeaderLabels(
            [
                "Album",
                "Titel",
                "Mehrheit",
                "Ø Bitrate",
                "Ø LUFS",
                "Album Gain",
                "Album Peak",
                "Technische Abweichungen",
                "Peak-Hinweise",
                "Nicht analysiert",
                "Gesundheit",
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

        for column in range(1, 11):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        return table

    def start_analysis(
        self,
        songs: list[Song],
    ):
        if not songs:
            return

        if not self.installation.available:
            QMessageBox.warning(
                self,
                "FFmpeg fehlt",
                "FFmpeg und ffprobe wurden nicht gefunden.",
            )
            return

        self.current_songs = list(songs)
        self.results.clear()
        self.track_table.setRowCount(0)
        self.album_table.setRowCount(0)
        self.log_output.clear()
        self.statistics_label.setText(
            "Analyse läuft …"
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
        self.thread.finished.connect(
            self.thread.deleteLater
        )

        self.thread.start()

    def cancel_analysis(self):
        if self.worker is not None:
            self.worker.cancel()
            self.status_label.setText(
                "Analyse wird abgebrochen …"
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
            (
                f"{total_count} Titel · "
                f"{cache_count} aus Cache · "
                f"{newly_analyzed_count} neu berechnet · "
                f"{elapsed_seconds:.2f} Sekunden · "
                f"Ø {average_seconds:.2f} Sekunden pro Titel"
            )
        )
        self.append_log(
            (
                "Analyse-Zusammenfassung\n"
                f"  Titel: {total_count}\n"
                f"  Aus Cache: {cache_count}\n"
                f"  Neu berechnet: {newly_analyzed_count}\n"
                f"  Dauer: {elapsed_seconds:.2f} Sekunden"
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
            (
                f"Analyse abgeschlossen: "
                f"{len(self.results)} Titel."
            )
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
            "Audioanalyse fehlgeschlagen",
            message,
        )

    def _refresh_track_table(self):
        ordered_results = [
            self.results[song.path]
            for song in self.current_songs
            if song.path in self.results
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
                    result.peak_status
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
                    "Cache"
                    if result.from_cache
                    else "Neu"
                ),
            ]

            if result.error:
                values[1] = "Fehler"
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

                tooltip_lines: list[str] = []

                if summary.technical_outliers:
                    tooltip_lines.append(
                        "Technische Abweichungen:\n"
                        + "\n".join(
                            summary.technical_outliers
                        )
                    )

                if summary.elevated_peak_files:
                    tooltip_lines.append(
                        "True Peak über 1 bis 2 dBTP:\n"
                        + "\n".join(
                            summary.elevated_peak_files
                        )
                    )

                if summary.critical_peak_files:
                    tooltip_lines.append(
                        "True Peak über 2 dBTP:\n"
                        + "\n".join(
                            summary.critical_peak_files
                        )
                    )

                if summary.missing_analysis_files:
                    tooltip_lines.append(
                        "Nicht analysiert:\n"
                        + "\n".join(
                            summary.missing_analysis_files
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
            "ReplayGain schreiben",
            (
                f"ReplayGain-Tags werden in "
                f"{len(valid_results)} Dateien geschrieben.\n\n"
                "Vorhandene ReplayGain-Tags überschreiben?"
            ),
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
            "ReplayGain-Tags werden geschrieben …",
            "Abbrechen",
            0,
            len(valid_results),
            self,
        )
        progress_dialog.setWindowTitle(
            "ReplayGain schreiben"
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
                (
                    f"{result.filename}\n"
                    f"{index} / {len(valid_results)}"
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

        message = (
            f"ReplayGain wurde in "
            f"{saved} Dateien geschrieben."
        )

        if progress_dialog.wasCanceled():
            message += (
                "\n\nDer Vorgang wurde abgebrochen."
            )

        if failures:
            message += (
                "\n\nFehler:\n"
                + "\n".join(failures)
            )

        QMessageBox.information(
            self,
            "ReplayGain abgeschlossen",
            message,
        )

    def closeEvent(self, event):
        if (
            self.thread is not None
            and self.thread.isRunning()
        ):
            answer = QMessageBox.question(
                self,
                "Analyse läuft",
                (
                    "Die Audioanalyse läuft noch. "
                    "Wirklich abbrechen und schließen?"
                ),
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
            self.thread.quit()
            self.thread.wait(3000)

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
) -> str:
    return {
        "normal": "Unauffällig",
        "elevated": "Erhöht",
        "critical": "Kritisch",
        "unknown": "Unbekannt",
    }.get(
        status,
        "Unbekannt",
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
