from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..i18n import tr
from ..models.song import Song
from ..services.convert import (
    BITRATE_CHOICES,
    FORMATS,
    convert_file,
    target_path,
)


class _ConvertWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(int, list)

    def __init__(self, songs, out_dir, fmt, bitrate) -> None:
        super().__init__()
        self._songs = songs
        self._out_dir = out_dir
        self._fmt = fmt
        self._bitrate = bitrate

    @Slot()
    def run(self) -> None:
        ok = 0
        errors: list[str] = []
        total = len(self._songs)
        for index, song in enumerate(self._songs):
            self.progress.emit(index, total, Path(song.path).name)
            try:
                dest = target_path(song.path, self._out_dir, self._fmt)
                convert_file(song.path, dest, self._fmt, bitrate=self._bitrate)
                ok += 1
            except Exception as error:  # noqa: BLE001
                errors.append(f"{Path(song.path).name}: {error}")
        self.finished.emit(ok, errors)


class ConversionDialog(QDialog):
    """Konvertiert ausgewählte Titel in ein Zielformat (neue Dateien)."""

    def __init__(
        self, songs: list[Song], parent=None, *, language: str = "automatic"
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.songs = [s for s in songs if s.path and Path(s.path).is_file()]
        self._thread: QThread | None = None
        self._worker: _ConvertWorker | None = None

        self.setWindowTitle(tr("convert_title", language))
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        info = QLabel(tr("convert_info", language, count=len(self.songs)))
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.format_combo = QComboBox()
        for fmt in FORMATS.values():
            self.format_combo.addItem(fmt.label, fmt.key)
        self.format_combo.currentIndexChanged.connect(self._update_bitrate_state)
        form.addRow(tr("convert_format", language), self.format_combo)

        self.bitrate_combo = QComboBox()
        for kbps in BITRATE_CHOICES:
            self.bitrate_combo.addItem(f"{kbps} kbit/s", kbps * 1000)
        self.bitrate_combo.setCurrentText("320 kbit/s")
        form.addRow(tr("convert_bitrate", language), self.bitrate_combo)

        output_row = QHBoxLayout()
        default_dir = (
            str(Path(self.songs[0].path).parent / "converted")
            if self.songs
            else ""
        )
        self.output_edit = QLineEdit(default_dir)
        browse = QPushButton(tr("convert_browse", language))
        browse.clicked.connect(self._browse)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(browse)
        form.addRow(tr("convert_output", language), output_row)
        layout.addLayout(form)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.close_button = QPushButton(tr("close_btn", language))
        self.close_button.clicked.connect(self.reject)
        self.start_button = QPushButton(tr("convert_start", language))
        self.start_button.setDefault(True)
        self.start_button.clicked.connect(self._start)
        self.start_button.setEnabled(bool(self.songs))
        buttons.addWidget(self.close_button)
        buttons.addWidget(self.start_button)
        layout.addLayout(buttons)

        self._update_bitrate_state()

    def _current_format(self):
        return FORMATS[self.format_combo.currentData()]

    def _update_bitrate_state(self) -> None:
        self.bitrate_combo.setEnabled(not self._current_format().lossless)

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, tr("convert_output", self.language), self.output_edit.text()
        )
        if directory:
            self.output_edit.setText(directory)

    def _start(self) -> None:
        out_dir = self.output_edit.text().strip()
        if not out_dir:
            QMessageBox.warning(
                self,
                tr("convert_title", self.language),
                tr("convert_pick_output", self.language),
            )
            return
        if self._thread is not None:
            return

        fmt = self._current_format()
        bitrate = int(self.bitrate_combo.currentData()) if not fmt.lossless else None

        self.start_button.setEnabled(False)
        self.format_combo.setEnabled(False)
        self.bitrate_combo.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.songs))
        self.progress.setValue(0)

        self._thread = QThread(self)
        self._worker = _ConvertWorker(list(self.songs), out_dir, fmt, bitrate)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()

    @Slot(int, int, str)
    def _on_progress(self, position: int, total: int, name: str) -> None:
        self.progress.setValue(position)
        self.status.setText(f"{min(position + 1, total)}/{total}: {name}")

    @Slot(int, list)
    def _on_finished(self, ok: int, errors: list) -> None:
        self.progress.setValue(self.progress.maximum())
        message = tr("convert_done", self.language, count=ok)
        if errors:
            message += "\n\n" + "\n".join(errors)
        self.status.setText(message)

    def _cleanup(self) -> None:
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self.start_button.setEnabled(True)
        self.format_combo.setEnabled(True)
        self._update_bitrate_state()
