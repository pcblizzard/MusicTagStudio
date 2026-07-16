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
from ..cover_management.comparison import compare_cover_candidates
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
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(3)
        self._active_workers: set[FunctionWorker] = set()
        self._closing = False
        self._preview_generation = 0
        self._preview_cache: dict[
            int,
            bytes,
        ] = {}
        self._preview_loading: set[
            int
        ] = set()

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
        self.refresh_button = QPushButton(
            "Online neu suchen"
        )
        self.direct_button.clicked.connect(
            self._start_direct_search
        )
        self.refresh_button.clicked.connect(
            self._start_refresh_search
        )

        direct_layout.addWidget(
            self.reference_edit,
            1,
        )
        direct_layout.addWidget(
            self.direct_button,
        )
        direct_layout.addWidget(
            self.refresh_button,
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
        right_side = QVBoxLayout()
        right_side.addWidget(self.preview)
        self.quality_label = QLabel(
            "Noch kein Cover ausgewählt."
        )
        self.quality_label.setWordWrap(True)
        self.quality_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        right_side.addWidget(
            self.quality_label
        )

        self.comparison_label = QLabel(
            "Für den Bildvergleich bitte ein Cover auswählen."
        )
        self.comparison_label.setWordWrap(True)
        right_side.addWidget(
            self.comparison_label
        )
        body.addLayout(
            right_side,
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

    def _start_refresh_search(self):
        self._start_search(
            None,
            force_refresh=True,
        )

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

        self._start_search(
            reference,
            force_refresh=True,
        )

    def _start_search(
        self,
        reference,
        force_refresh: bool = False,
    ):
        self.direct_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.status_label.setText(
            "Coverquellen werden parallel durchsucht …"
        )
        self.list.clear()
        self.candidates.clear()
        self._preview_cache.clear()
        self._preview_loading.clear()
        self.ok_button.setEnabled(False)
        self.preview.clear()
        self.preview.setText(
            "Suche läuft …"
        )

        worker = FunctionWorker(
            self.manager.search_candidates,
            self.song,
            reference,
            force_refresh,
        )
        worker.signals.finished.connect(
            self._search_finished
        )
        worker.signals.failed.connect(
            self._search_failed
        )
        self._start_worker(worker)

    def _start_worker(
        self,
        worker: FunctionWorker,
    ) -> None:
        if self._closing:
            return

        self._active_workers.add(
            worker
        )
        worker.signals.finished.connect(
            lambda _result, current=worker:
            self._release_worker(current)
        )
        worker.signals.failed.connect(
            lambda _message, current=worker:
            self._release_worker(current)
        )
        self.thread_pool.start(
            worker
        )

    def _release_worker(
        self,
        worker: FunctionWorker,
    ) -> None:
        self._active_workers.discard(
            worker
        )

    def _search_finished(
        self,
        result,
    ):
        if self._closing:
            return

        self.direct_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
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

        best = max(
            self.candidates,
            key=lambda candidate:
            candidate.score,
        )
        self.status_label.setText(
            f"{len(self.candidates)} Cover gefunden. "
            f"Empfehlung: {best.source_label} "
            f"({best.score} Punkte)."
        )
        best_row = self.candidates.index(
            best
        )
        self.list.setCurrentRow(
            best_row
        )
        self.ok_button.setEnabled(True)
        self._prefetch_previews(
            preferred_row=best_row
        )

    def _search_failed(
        self,
        message: str,
    ):
        if self._closing:
            return

        self.direct_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
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
        self._update_quality_label(
            candidate
        )

        data = (
            candidate.data
            or self._preview_cache.get(
                row
            )
        )

        if data is not None:
            self._show_preview_data(
                data,
                candidate,
            )
            return

        self._preview_generation += 1
        generation = self._preview_generation
        self.preview.clear()
        self.preview.setText(
            "Vorschau wird im Hintergrund geladen …"
        )
        self._start_preview_download(
            row,
            generation=generation,
        )

    def _prefetch_previews(
        self,
        *,
        preferred_row: int,
    ) -> None:
        """
        Lädt die kleinen Vorschaubilder sofort nach der Suche parallel vor.
        Beim späteren Anklicken ist das Bild dadurch meistens bereits im RAM.
        """
        rows = [
            preferred_row,
            *(
                row
                for row in range(
                    len(self.candidates)
                )
                if row != preferred_row
            ),
        ]

        # Nicht sämtliche Onlinequellen gleichzeitig starten. Das hält den
        # Dialog reaktionsfähig und vermeidet viele späte Rückrufe beim
        # Schließen. Die aktuell gewählte Vorschau und höchstens zwei weitere
        # Treffer werden vorbereitet.
        for row in rows[:3]:
            candidate = self.candidates[
                row
            ]

            if candidate.data is not None:
                self._preview_cache[
                    row
                ] = candidate.data
                continue

            self._start_preview_download(
                row
            )

    def _start_preview_download(
        self,
        row: int,
        *,
        generation: int | None = None,
    ) -> None:
        if (
            self._closing
            or row in self._preview_cache
            or row in self._preview_loading
            or row < 0
            or row >= len(
                self.candidates
            )
        ):
            return

        candidate = self.candidates[
            row
        ]
        self._preview_loading.add(
            row
        )
        worker = FunctionWorker(
            self._load_preview_result,
            row,
            generation,
            candidate,
        )
        worker.signals.finished.connect(
            self._preview_finished
        )
        worker.signals.failed.connect(
            self._preview_failed
        )
        self._start_worker(
            worker
        )

    def _load_preview_result(
        self,
        row: int,
        generation: int | None,
        candidate: CoverCandidate,
    ):
        data = self.manager.load_preview(
            candidate
        )

        return (
            row,
            generation,
            candidate,
            data,
        )

    @Slot(object)
    def _preview_finished(
        self,
        result,
    ) -> None:
        if self._closing:
            return

        (
            row,
            generation,
            candidate,
            data,
        ) = result
        self._preview_loading.discard(
            row
        )

        if (
            row < 0
            or row >= len(
                self.candidates
            )
            or self.candidates[row]
            is not candidate
        ):
            return

        self._preview_cache[
            row
        ] = data

        if (
            self.list.currentRow()
            == row
            and (
                generation is None
                or generation
                == self._preview_generation
            )
        ):
            self._show_preview_data(
                data,
                candidate,
            )

    @Slot(str)
    def _preview_failed(
        self,
        message: str,
    ) -> None:
        if self._closing:
            return

        current_row = (
            self.list.currentRow()
        )

        if current_row >= 0:
            self._preview_loading.discard(
                current_row
            )

        if (
            current_row >= 0
            and current_row
            not in self._preview_cache
        ):
            self.preview.setText(
                "Vorschau nicht verfügbar\n"
                + message
            )

    def _show_preview_data(
        self,
        data: bytes,
        candidate: CoverCandidate,
    ):
        pixmap = QPixmap()

        if not pixmap.loadFromData(data):
            self.preview.setText(
                "Vorschau konnte nicht geladen werden"
            )
            return

        self._update_quality_label(
            candidate,
            preview_size=len(data),
            preview_width=pixmap.width(),
            preview_height=pixmap.height(),
        )

        self.preview.setPixmap(
            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _update_quality_label(
        self,
        candidate: CoverCandidate,
        *,
        preview_size: int | None = None,
        preview_width: int | None = None,
        preview_height: int | None = None,
    ):
        source = candidate.source_label
        original_dimensions = (
            candidate.dimensions
        )
        original_format = (
            candidate.mime
            or "wird beim Originaldownload ermittelt"
        )
        original_size = (
            candidate.file_size_text
            if candidate.file_size
            else "wird beim Originaldownload ermittelt"
        )
        shape = (
            "quadratisch"
            if (
                candidate.width
                and candidate.width
                == candidate.height
            )
            else (
                "nicht quadratisch"
                if candidate.width
                and candidate.height
                else "noch nicht bekannt"
            )
        )

        lines = [
            f"Quelle: {source}",
            f"Originalauflösung: {original_dimensions}",
            f"Originalformat: {original_format}",
            f"Originalgröße: {original_size}",
            f"Seitenverhältnis: {shape}",
            f"Bewertung: {candidate.score} / 100",
            (
                f"MD5: {candidate.short_hash}"
                if candidate.short_hash
                else "MD5: wird beim Originaldownload berechnet"
            ),
        ]

        if (
            preview_size is not None
            and preview_width is not None
            and preview_height is not None
        ):
            lines.extend(
                [
                    "",
                    (
                        "Geladene Vorschau: "
                        f"{preview_width} × {preview_height}"
                    ),
                    (
                        "Vorschaugröße: "
                        f"{preview_size / 1024:.1f} KB"
                    ),
                ]
            )

        self.quality_label.setText(
            "\n".join(lines)
        )

        local_candidates = [
            item
            for item in self.candidates
            if item.is_local
        ]

        if (
            local_candidates
            and candidate is not local_candidates[0]
        ):
            comparison = compare_cover_candidates(
                local_candidates[0],
                candidate,
            )
            self.comparison_label.setText(
                "Vergleich mit vorhandenem Master-Cover:\n"
                + comparison.description
            )
        elif candidate.is_local:
            self.comparison_label.setText(
                "Vorhandenes Master-Cover."
            )
        else:
            self.comparison_label.setText(
                "Kein vorhandenes Master-Cover zum Vergleichen."
            )

    def reject(self) -> None:
        self._prepare_close()
        super().reject()

    def accept(self) -> None:
        self._prepare_close()
        super().accept()

    def closeEvent(
        self,
        event,
    ) -> None:
        self._prepare_close()
        super().closeEvent(
            event
        )

    def _prepare_close(
        self,
    ) -> None:
        if self._closing:
            return

        self._closing = True
        self._preview_generation += 1
        self._preview_loading.clear()

        # Die Aufgaben dürfen sauber auslaufen, ihre Ergebnisse werden nach
        # dem Schließen aber nicht mehr an Widgets weitergereicht.
        for worker in tuple(
            self._active_workers
        ):
            try:
                worker.signals.finished.disconnect(
                    self._search_finished
                )
            except (
                RuntimeError,
                TypeError,
            ):
                pass

            try:
                worker.signals.failed.disconnect(
                    self._search_failed
                )
            except (
                RuntimeError,
                TypeError,
            ):
                pass

            try:
                worker.signals.finished.disconnect(
                    self._preview_finished
                )
            except (
                RuntimeError,
                TypeError,
            ):
                pass

            try:
                worker.signals.failed.disconnect(
                    self._preview_failed
                )
            except (
                RuntimeError,
                TypeError,
            ):
                pass

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
