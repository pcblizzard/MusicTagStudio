from __future__ import annotations

from collections import defaultdict
from pathlib import Path

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
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
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


WARNING_BACKGROUND = QColor(
    92,
    66,
    38,
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
    finished = Signal()
    failed = Signal(str)

    def __init__(
        self,
        songs: list[Song],
        installation: FFmpegInstallation,
        calculate_album_gain: bool,
    ):
        super().__init__()
        self.songs = songs
        self.installation = installation
        self.calculate_album_gain = (
            calculate_album_gain
        )
        self.cancelled = False

    @Slot()
    def run(self):
        try:
            total = len(self.songs)

            for index, song in enumerate(
                self.songs,
                start=1,
            ):
                if self.cancelled:
                    break

                self.progress.emit(
                    index - 1,
                    total,
                    Path(song.path).name,
                )
                result = analyze_file(
                    song.path,
                    self.installation,
                )
                self.result_ready.emit(
                    result
                )

            if (
                not self.cancelled
                and self.calculate_album_gain
            ):
                grouped: dict[
                    tuple[str, str],
                    list[Song],
                ] = defaultdict(list)

                for song in self.songs:
                    key = (
                        song.album_artist
                        or song.artist,
                        song.album,
                    )
                    grouped[key].append(song)

                for album_index, (
                    key,
                    album_songs,
                ) in enumerate(
                    grouped.items(),
                    start=1,
                ):
                    if self.cancelled:
                        break

                    self.progress.emit(
                        total,
                        total,
                        (
                            "Album-ReplayGain: "
                            f"{key[0]} – {key[1]}"
                        ),
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

            self.progress.emit(
                total,
                total,
                "Analyse abgeschlossen",
            )
            self.finished.emit()
        except Exception as error:
            self.failed.emit(
                str(error)
            )

    @Slot()
    def cancel(self):
        self.cancelled = True


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

        self.setWindowTitle(
            "Audio-Analyse"
        )
        self.resize(
            1400,
            760,
        )

        layout = QVBoxLayout(self)

        if self.installation.available:
            status_text = (
                "FFmpeg gefunden: "
                f"{self.installation.version}\n"
                f"{self.installation.ffmpeg_path}"
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
        self.track_table = self._create_track_table()
        self.album_table = self._create_album_table()
        self.tabs.addTab(
            self.track_table,
            "Titelanalyse",
        )
        self.tabs.addTab(
            self.album_table,
            "Albumvergleich",
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
        table.setColumnCount(15)
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
                "Clipping",
                "Track Gain",
                "Track Peak",
                "Album Gain",
                "Album Peak",
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

        for column in range(1, 15):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        return table

    def _create_album_table(
        self,
    ) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            [
                "Album",
                "Titel",
                "Mehrheit",
                "Technische Abweichungen",
                "Clipping-Hinweise",
                "Nicht analysiert",
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

        for column in range(1, 6):
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
                "Analyse wird nach der aktuellen Datei abgebrochen …"
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
                    song.album_artist
                    or song.artist,
                    song.album,
                )
                == tuple(album_key)
            )
        ]

        for song in album_songs:
            result = self.results.get(
                song.path
            )

            if result is None:
                continue

            self.results[
                song.path
            ] = (
                result.with_album_replaygain(
                    gain,
                    peak,
                )
            )

        self._refresh_track_table()

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
                and result.replaygain_track_gain_db
                is not None
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
                (
                    "Ja"
                    if result.clipping_warning
                    else "Nein"
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
                elif result.clipping_warning:
                    item.setBackground(
                        WARNING_BACKGROUND
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
                str(
                    len(
                        summary.technical_outliers
                    )
                ),
                str(
                    len(
                        summary.clipping_files
                    )
                ),
                str(
                    len(
                        summary.missing_analysis_files
                    )
                ),
            ]

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    value
                )

                if summary.has_warnings:
                    item.setBackground(
                        WARNING_BACKGROUND
                    )

                tooltip_lines: list[str] = []

                if summary.technical_outliers:
                    tooltip_lines.append(
                        "Technische Abweichungen:\n"
                        + "\n".join(
                            summary.technical_outliers
                        )
                    )

                if summary.clipping_files:
                    tooltip_lines.append(
                        "Clipping-Hinweise:\n"
                        + "\n".join(
                            summary.clipping_files
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
                and result.replaygain_track_gain_db
                is not None
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

        saved = 0
        failures: list[str] = []

        for result in valid_results:
            try:
                write_replaygain_tags(
                    result,
                    overwrite=overwrite,
                )
            except Exception as error:
                failures.append(
                    f"{result.filename}: {error}"
                )
                continue

            saved += 1

        message = (
            f"ReplayGain wurde in "
            f"{saved} Dateien geschrieben."
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
                "Die Audioanalyse läuft noch. Wirklich abbrechen und schließen?",
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
