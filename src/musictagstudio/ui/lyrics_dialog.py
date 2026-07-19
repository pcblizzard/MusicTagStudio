from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ..lyrics import (
    LyricsDocument,
    LyricsRequest,
    LyricsResolution,
    LyricsResolver,
    read_duration_seconds,
    save_sidecar,
)
from ..models.song import Song


class LyricsWorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class LyricsWorker(QRunnable):
    def __init__(self, function, *args, **kwargs) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = LyricsWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function(*self.args, **self.kwargs)
        except Exception as error:
            self.signals.failed.emit(str(error))
            return
        self.signals.finished.emit(result)


class LyricsDialog(QDialog):
    def __init__(
        self,
        song: Song,
        parent=None,
        *,
        resolver: LyricsResolver | None = None,
    ) -> None:
        super().__init__(parent)
        self.song = song
        self.resolver = resolver or LyricsResolver()
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: set[LyricsWorker] = set()
        self._closing = False
        self.documents: list[LyricsDocument] = []
        self.request = LyricsRequest(
            audio_path=song.path,
            title=song.title,
            artist=song.artist,
            album=song.album,
            duration=read_duration_seconds(song.path),
        )
        self._lrclib_ready = bool(
            self.request.title.strip()
            and self.request.artist.strip()
            and self.request.album.strip()
            and self.request.duration > 0
        )

        self.setWindowTitle(f"Lyrics · {song.title or 'Unbekannter Titel'}")
        self.resize(780, 680)
        layout = QVBoxLayout(self)

        title = QLabel(song.title or "Unbekannter Titel")
        title.setObjectName("lyricsTitle")
        title.setStyleSheet("font-size: 19px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel(f"{song.artist or 'Unbekannter Künstler'} · {song.album or 'Ohne Album'}"))

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Quelle:"))
        self.source_combo = QComboBox()
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        source_row.addWidget(self.source_combo, stretch=1)
        layout.addLayout(source_row)

        self.source_details = QLabel()
        self.source_details.setStyleSheet("color: palette(mid);")
        layout.addWidget(self.source_details)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setObjectName("lyricsWarning")
        self.warning_label.setStyleSheet(
            "padding: 9px; border: 1px solid #d69e2e; "
            "border-radius: 7px; background: rgba(214, 158, 46, 35);"
        )
        self.warning_label.hide()
        layout.addWidget(self.warning_label)

        self.lyrics_text = QPlainTextEdit()
        self.lyrics_text.setObjectName("lyricsDisplay")
        self.lyrics_text.setReadOnly(True)
        self.lyrics_text.setPlaceholderText("Keine Lyrics aus lokalen Quellen gefunden.")
        layout.addWidget(self.lyrics_text, stretch=1)

        actions = QHBoxLayout()
        self.cached_button = QPushButton("LRCLIB prüfen")
        self.cached_button.setToolTip(
            "Fragt nur bereits bei LRCLIB gespeicherte Lyrics ab."
        )
        self.cached_button.clicked.connect(lambda: self._load_online(live=False))
        actions.addWidget(self.cached_button)
        self.live_button = QPushButton("LRCLIB live suchen")
        self.live_button.setToolTip(
            "Bewusste Live-Abfrage; LRCLIB kann dafür weitere externe Quellen prüfen."
        )
        self.live_button.clicked.connect(lambda: self._load_online(live=True))
        actions.addWidget(self.live_button)
        actions.addStretch()
        self.save_button = QPushButton("Als LRC speichern")
        self.save_button.clicked.connect(self._save_selected)
        self.save_button.setEnabled(False)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        if not self._lrclib_ready:
            self.status_label.setText(
                "LRCLIB benötigt Titel, Künstler, Album und eine lesbare Titeldauer. "
                "Lokale Lyrics können weiterhin verwendet werden."
            )
            self.cached_button.setEnabled(False)
            self.live_button.setEnabled(False)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._apply_resolution(self.resolver.local(self.request))

    def _apply_resolution(self, resolution: LyricsResolution) -> None:
        self.documents = list(resolution.candidates)
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for document in self.documents:
            kind = "synchronisiert" if document.is_synced else "unsynchronisiert"
            if document.instrumental:
                kind = "Instrumental"
            self.source_combo.addItem(f"{document.source} · {kind}")
        self.source_combo.blockSignals(False)
        if resolution.selected in self.documents:
            self.source_combo.setCurrentIndex(
                self.documents.index(resolution.selected)
            )
        elif self.documents:
            self.source_combo.setCurrentIndex(0)
        self._show_document(self.current_document(), resolution.warning)

    def current_document(self) -> LyricsDocument | None:
        index = self.source_combo.currentIndex()
        if 0 <= index < len(self.documents):
            return self.documents[index]
        return None

    def _source_changed(self, _index: int) -> None:
        document = self.current_document()
        from ..lyrics.resolver import live_version_warning

        self._show_document(
            document,
            live_version_warning(self.request, document),
        )

    def _show_document(
        self,
        document: LyricsDocument | None,
        warning: str = "",
    ) -> None:
        if document is None:
            self.lyrics_text.clear()
            self.source_details.setText("Keine lokale Quelle vorhanden")
            self.save_button.setEnabled(False)
        else:
            self.lyrics_text.setPlainText(document.display_text())
            details = [document.source]
            if document.provider_id:
                details.append(f"ID {document.provider_id}")
            if document.fetched_at:
                details.append(f"abgerufen {document.fetched_at}")
            self.source_details.setText(" · ".join(details))
            self.save_button.setEnabled(not document.is_empty)
        self.warning_label.setText(warning)
        self.warning_label.setVisible(bool(warning))

    def _load_online(self, *, live: bool) -> None:
        if not self._lrclib_ready:
            return
        self._set_loading(True)
        self.status_label.setText(
            "LRCLIB wird live durchsucht …"
            if live
            else "LRCLIB-Cache wird geprüft …"
        )
        worker = LyricsWorker(self.resolver.online, self.request, live=live)
        self._workers.add(worker)
        worker.signals.finished.connect(self._online_loaded)
        worker.signals.failed.connect(self._online_failed)
        worker.signals.finished.connect(lambda _result, item=worker: self._release_worker(item))
        worker.signals.failed.connect(lambda _error, item=worker: self._release_worker(item))
        self.thread_pool.start(worker)

    def _online_loaded(self, resolution: LyricsResolution) -> None:
        if self._closing:
            return
        self._set_loading(False)
        self.status_label.setText("Lyrics wurden geladen und lokal zwischengespeichert.")
        self._apply_resolution(resolution)

    def _online_failed(self, message: str) -> None:
        if self._closing:
            return
        self._set_loading(False)
        self.status_label.setText(message)

    def _release_worker(self, worker: LyricsWorker) -> None:
        self._workers.discard(worker)

    def _set_loading(self, loading: bool) -> None:
        enabled = self._lrclib_ready and not loading
        self.cached_button.setEnabled(enabled)
        self.live_button.setEnabled(enabled)

    def _save_selected(self) -> None:
        document = self.current_document()
        if document is None:
            return
        try:
            destination = save_sidecar(self.song.path, document)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Lyrics speichern", str(error))
            return
        self.status_label.setText(f"Gespeichert: {destination}")
        self._apply_resolution(self.resolver.local(self.request))

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        super().closeEvent(event)
