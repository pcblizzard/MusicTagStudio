from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..audio_analysis.dedupe import (
    DuplicateGroup,
    build_track,
    find_duplicate_groups,
)
from ..i18n import tr
from ..models.song import Song

_KEEP_BACKGROUND = QColor(214, 245, 222)


def _duration_text(seconds: float) -> str:
    if seconds <= 0:
        return ""
    total = round(seconds)
    return f"{total // 60}:{total % 60:02d}"


class _DedupeWorker(QObject):
    finished = Signal(object)  # list[DuplicateGroup]
    failed = Signal(str)

    def __init__(self, songs: list[Song]) -> None:
        super().__init__()
        self._songs = songs

    @Slot()
    def run(self) -> None:
        try:
            tracks = [
                build_track(
                    path=song.path,
                    artist=song.artist,
                    title=song.title,
                    album=song.album,
                )
                for song in self._songs
                if song.path and Path(song.path).is_file()
            ]
            self.finished.emit(find_duplicate_groups(tracks))
        except Exception as error:  # pragma: no cover - Schutz vor Absturz
            self.failed.emit(str(error))


class DuplicatesDialog(QDialog):
    """Findet Duplikate und lässt schlechtere Kopien in den Papierkorb legen."""

    songs_deleted = Signal(list)  # entfernte Pfade

    def __init__(
        self,
        all_songs: list[Song],
        parent=None,
        *,
        embedded: bool = False,
        language: str = "automatic",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.embedded = embedded
        self.all_songs = list(all_songs)
        self._thread: QThread | None = None
        self._worker: _DedupeWorker | None = None

        if not embedded:
            self.setWindowTitle(tr("duplicates", language))
            self.resize(1000, 640)
        else:
            self.setWindowFlags(Qt.WindowType.Widget)

        layout = QVBoxLayout(self)

        intro = QLabel(tr("dup_intro", language))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.scan_button = QPushButton(tr("dup_scan_btn", language))
        self.scan_button.clicked.connect(self._start_scan)
        layout.addWidget(self.scan_button)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(
            [
                tr("dup_col_file", language),
                tr("dup_col_quality", language),
                tr("dup_col_duration", language),
                tr("dup_col_status", language),
            ]
        )
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tree.setRootIsDecorated(True)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        layout.addWidget(self.tree)

        self.delete_button = QPushButton(tr("dup_delete_btn", language))
        self.delete_button.clicked.connect(self._delete_checked)
        self.delete_button.setEnabled(False)
        layout.addWidget(self.delete_button)

    def set_songs(self, all_songs: list[Song]) -> None:
        self.all_songs = list(all_songs)

    # --- Scan ---------------------------------------------------------------

    def _start_scan(self) -> None:
        if self._thread is not None:
            return
        if not self.all_songs:
            self.status_label.setText(tr("dup_scan_first", self.language))
            return

        self.scan_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.tree.clear()
        self.status_label.setText(tr("dup_scanning", self.language))

        self._thread = QThread(self)
        self._worker = _DedupeWorker(list(self.all_songs))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.failed.connect(self._on_scan_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)
        self._thread.start()

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self.scan_button.setEnabled(True)

    @Slot(object)
    def _on_scan_finished(self, groups: list[DuplicateGroup]) -> None:
        self._populate(groups)

    @Slot(str)
    def _on_scan_failed(self, message: str) -> None:
        self.status_label.setText(message)

    def _populate(self, groups: list[DuplicateGroup]) -> None:
        self.tree.clear()
        if not groups:
            self.status_label.setText(tr("dup_none", self.language))
            self.delete_button.setEnabled(False)
            return

        removable = sum(len(group.removable) for group in groups)
        self.status_label.setText(
            tr(
                "dup_summary",
                self.language,
                groups=len(groups),
                removable=removable,
            )
        )

        for group in groups:
            parent = QTreeWidgetItem(
                [f"{group.keep.artist} – {group.keep.title}", "", "", ""]
            )
            parent.setFirstColumnSpanned(True)
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(parent)

            for track in group.tracks:
                is_keep = track.path == group.keep.path
                child = QTreeWidgetItem(
                    [
                        track.filename,
                        track.quality.summary(),
                        _duration_text(track.duration),
                        tr("dup_keep", self.language) if is_keep else "",
                    ]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, track.path)
                if is_keep:
                    child.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    for column in range(4):
                        child.setBackground(column, _KEEP_BACKGROUND)
                        child.setForeground(column, QColor(35, 42, 38))
                else:
                    child.setFlags(
                        Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    child.setCheckState(0, Qt.CheckState.Checked)
                parent.addChild(child)
            parent.setExpanded(True)

        self.delete_button.setEnabled(removable > 0)

    # --- Löschen ------------------------------------------------------------

    def _checked_paths(self) -> list[str]:
        paths: list[str] = []
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if (
                    child.flags() & Qt.ItemFlag.ItemIsUserCheckable
                    and child.checkState(0) == Qt.CheckState.Checked
                ):
                    path = child.data(0, Qt.ItemDataRole.UserRole)
                    if path:
                        paths.append(str(path))
        return paths

    def _delete_checked(self) -> None:
        paths = self._checked_paths()
        if not paths:
            return

        answer = QMessageBox.question(
            self,
            tr("dup_delete_btn", self.language),
            tr("dup_delete_confirm", self.language, count=len(paths)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        from send2trash import send2trash

        deleted: list[str] = []
        errors: list[str] = []
        for path in paths:
            try:
                send2trash(path)
                deleted.append(path)
            except Exception as error:  # noqa: BLE001
                errors.append(f"{Path(path).name}: {error}")

        if deleted:
            removed = set(deleted)
            self.all_songs = [
                song for song in self.all_songs if song.path not in removed
            ]
            self.songs_deleted.emit(deleted)

        message = tr("dup_deleted", self.language, count=len(deleted))
        if errors:
            message += "\n\n" + "\n".join(errors)
        QMessageBox.information(
            self, tr("dup_delete_btn", self.language), message
        )
        self._start_scan()
