from __future__ import annotations

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ..cover_management.manager import CoverManager
from ..cover_management.models import CoverCandidate
from ..direct_references import (
    DirectAlbumReferenceError,
    parse_album_reference,
)
from ..models.song import Song


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class FunctionWorker(QRunnable):
    def __init__(
        self,
        function,
        *args,
        **kwargs,
    ):
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
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

        self.signals.finished.emit(result)


class CoverSelectionDialog(QDialog):
    def __init__(
        self,
        manager: CoverManager,
        song: Song,
        parent=None,
    ):
        super().__init__(parent)

        self.manager = manager
        self.song = song
        self.candidates: list[
            CoverCandidate
        ] = []
        self.selected_candidate: (
            CoverCandidate | None
        ) = None
        self.thread_pool = QThreadPool.globalInstance()
        self._preview_generation = 0

        self.setWindowTitle("Cover auswählen")
        self.resize(980, 650)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Der Dialog wird sofort geöffnet. "
            "Die Coverquellen werden parallel abgefragt und "
            "die Originaldatei wird erst nach der Auswahl heruntergeladen."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        direct_layout = QHBoxLayout()
        self.reference_edit = QLineEdit()
        self.reference_edit.setPlaceholderText(
            "Optional: Apple-Music-Albumlink, Apple-ID, "
            "MusicBrainz-Release-Link oder MBID"
        )
        self.direct_button = QPushButton(
            "Direkt laden"
        )
        self.direct_button.clicked.connect(
            self._start_direct_search
        )

        direct_layout.addWidget(
            self.reference_edit,
            1,
        )
        direct_layout.addWidget(
            self.direct_button,
        )
        layout.addLayout(direct_layout)

        self.status_label = QLabel(
            "Coverquellen werden durchsucht …"
        )
        layout.addWidget(
            self.status_label
        )

        body = QHBoxLayout()
        self.list = QListWidget()
        self.preview = QLabel(
            "Vorschau wird nach Auswahl geladen"
        )
        self.preview.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.preview.setFixedSize(
            440,
            440,
        )
        self.preview.setStyleSheet(
            "QLabel {"
            " border: 1px solid palette(mid);"
            " padding: 8px;"
            "}"
        )

        self.list.currentRowChanged.connect(
            self._load_preview
        )
        body.addWidget(
            self.list,
            1,
        )
        body.addWidget(
            self.preview,
            1,
        )
        layout.addLayout(body)

        buttons = QDialogButtonBox()
        self.ok_button = QPushButton(
            "Cover übernehmen"
        )
        cancel = QPushButton(
            "Abbrechen"
        )
        buttons.addButton(
            self.ok_button,
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        buttons.addButton(
            cancel,
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.ok_button.clicked.connect(
            self._accept
        )
        cancel.clicked.connect(
            self.reject
        )
        self.ok_button.setEnabled(False)
        layout.addWidget(buttons)

        self._start_search(None)

    def _start_direct_search(self):
        try:
            reference = parse_album_reference(
                self.reference_edit.text()
            )
        except DirectAlbumReferenceError as error:
            self.status_label.setText(
                str(error)
            )
            return

        self._start_search(reference)

    def _start_search(self, reference):
        self.direct_button.setEnabled(False)
        self.status_label.setText(
            "Coverquellen werden parallel durchsucht …"
        )
        self.list.clear()
        self.candidates.clear()
        self.ok_button.setEnabled(False)
        self.preview.clear()
        self.preview.setText(
            "Suche läuft …"
        )

        worker = FunctionWorker(
            self.manager.search_candidates,
            self.song,
            reference,
        )
        worker.signals.finished.connect(
            self._search_finished
        )
        worker.signals.failed.connect(
            self._search_failed
        )
        self.thread_pool.start(worker)

    def _search_finished(
        self,
        result,
    ):
        self.direct_button.setEnabled(True)
        self.candidates = list(result)

        if not self.candidates:
            self.status_label.setText(
                "Keine passenden Cover gefunden."
            )
            self.preview.setText(
                "Keine Vorschau"
            )
            return

        for candidate in self.candidates:
            details = (
                f"{candidate.source_label} · "
                f"{candidate.dimensions} · "
                f"Bewertung {candidate.score}"
            )

            if candidate.album:
                details += (
                    f"\n{candidate.artist} – "
                    f"{candidate.album}"
                )

            self.list.addItem(
                QListWidgetItem(details)
            )

        self.status_label.setText(
            f"{len(self.candidates)} Cover gefunden. "
            "Vorschaubilder werden nur bei Auswahl geladen."
        )
        self.list.setCurrentRow(0)
        self.ok_button.setEnabled(True)

    def _search_failed(
        self,
        message: str,
    ):
        self.direct_button.setEnabled(True)
        self.status_label.setText(
            f"Cover-Suche fehlgeschlagen: {message}"
        )
        self.preview.setText(
            "Keine Vorschau"
        )

    def _load_preview(
        self,
        row: int,
    ):
        if (
            row < 0
            or row >= len(self.candidates)
        ):
            return

        candidate = self.candidates[row]

        if candidate.data is not None:
            self._show_preview_data(
                candidate.data
            )
            return

        self._preview_generation += 1
        generation = self._preview_generation
        self.preview.clear()
        self.preview.setText(
            "Vorschau wird geladen …"
        )

        worker = FunctionWorker(
            self.manager.load_preview,
            candidate,
        )

        def show_if_current(data):
            if (
                generation
                != self._preview_generation
            ):
                return

            self._show_preview_data(data)

        worker.signals.finished.connect(
            show_if_current
        )
        worker.signals.failed.connect(
            lambda message:
            self.preview.setText(
                f"Vorschau nicht verfügbar\n{message}"
            )
        )
        self.thread_pool.start(worker)

    def _show_preview_data(
        self,
        data: bytes,
    ):
        pixmap = QPixmap()

        if not pixmap.loadFromData(data):
            self.preview.setText(
                "Vorschau konnte nicht geladen werden"
            )
            return

        self.preview.setPixmap(
            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _accept(self):
        row = self.list.currentRow()

        if (
            row < 0
            or row >= len(self.candidates)
        ):
            return

        self.selected_candidate = (
            self.candidates[row]
        )
        self.accept()
