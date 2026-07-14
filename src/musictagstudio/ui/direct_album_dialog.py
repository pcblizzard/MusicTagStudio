from __future__ import annotations

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
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
    DirectAlbumLookupError,
    lookup_album,
    match_album_tracks,
)
from ..direct_references import (
    DirectAlbumReferenceError,
    parse_album_reference,
)
from ..models.song import Song


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
    ):
        super().__init__(parent)

        self.songs = songs
        self.apple_country = apple_country
        self.result = None
        self.matches: dict = {}
        self.reference = None
        self.thread_pool = QThreadPool.globalInstance()

        self.setWindowTitle(
            "Album über Anbieter-Link laden"
        )
        self.resize(900, 600)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Gib einen direkten Apple-Music-Albumlink beziehungsweise "
            "eine Apple-Album-ID oder einen MusicBrainz-Release-Link "
            "beziehungsweise eine MBID ein. "
            "MusicTagStudio lädt genau dieses Album und ordnet die "
            "lokalen Dateien anhand von Disc-, Tracknummer und Titel zu."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText(
            "https://music.apple.com/album/.../1775980788"
        )
        self.load_button = QPushButton(
            "Album laden"
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
            "Noch kein Album geladen."
        )
        layout.addWidget(
            self.status_label
        )

        self.table = QTableWidget(
            len(songs),
            5,
        )
        self.table.setHorizontalHeaderLabels(
            [
                "Lokale Datei",
                "Lokaler Titel",
                "Zugeordneter Titel",
                "Track",
                "Status",
            ]
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

        buttons = QDialogButtonBox()
        self.compare_button = QPushButton(
            "Metadaten vergleichen"
        )
        cancel = QPushButton(
            "Abbrechen"
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
                "Ungültiger Album-Link",
                str(error),
            )
            return

        self.reference = reference
        self.load_button.setEnabled(False)
        self.compare_button.setEnabled(False)
        self.status_label.setText(
            "Album und Trackliste werden geladen …"
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

    def _loaded(self, result):
        self.load_button.setEnabled(True)
        self.result = result
        self.matches = match_album_tracks(
            self.songs,
            result,
        )

        for row, song in enumerate(self.songs):
            track = self.matches.get(row)

            if track is None:
                self.table.setItem(
                    row,
                    2,
                    QTableWidgetItem(""),
                )
                self.table.setItem(
                    row,
                    3,
                    QTableWidgetItem(""),
                )
                self.table.setItem(
                    row,
                    4,
                    QTableWidgetItem(
                        "Nicht eindeutig zugeordnet"
                    ),
                )
                continue

            self.table.setItem(
                row,
                2,
                QTableWidgetItem(track.title),
            )
            self.table.setItem(
                row,
                3,
                QTableWidgetItem(
                    f"{track.disc}/{track.track}"
                ),
            )
            self.table.setItem(
                row,
                4,
                QTableWidgetItem(
                    "Zugeordnet"
                ),
            )

        self.status_label.setText(
            f"{result.album_artist} – {result.album}: "
            f"{len(self.matches)} von {len(self.songs)} "
            "lokalen Dateien wurden zugeordnet."
        )
        self.compare_button.setEnabled(
            bool(self.matches)
        )

    def _failed(
        self,
        message: str,
    ):
        self.load_button.setEnabled(True)
        self.status_label.setText(
            f"Album konnte nicht geladen werden: {message}"
        )

    def _accept(self):
        if (
            self.result is None
            or not self.matches
        ):
            return

        self.accept()
