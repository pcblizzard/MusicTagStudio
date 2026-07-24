from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ..models.song import Song
from .engine import PlayerEngine


class QueueListWidget(QListWidget):
    order_changed = Signal()

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        if event.isAccepted():
            self.order_changed.emit()


class QueueDialog(QDialog):
    def __init__(self, engine: PlayerEngine, parent=None) -> None:
        super().__init__(parent)
        self.engine = engine
        self.settings = QSettings("MusicTagStudio", "MusicTagStudio")
        self._songs_by_id: dict[int, Song] = {}
        self._updating = False
        self.setWindowTitle("Warteschlange")
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)

        self.list = QueueListWidget()
        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list.setAlternatingRowColors(True)
        self.list.setAccessibleName("Titel in der Warteschlange")
        layout.addWidget(self.list, 1)

        actions = QHBoxLayout()
        self.play_button = QPushButton("Jetzt abspielen")
        self.next_button = QPushButton("Als Nächstes")
        self.remove_button = QPushButton("Aus Warteschlange entfernen")
        self.clear_button = QPushButton("Warteschlange leeren")
        actions.addWidget(self.play_button)
        actions.addWidget(self.next_button)
        actions.addWidget(self.remove_button)
        actions.addStretch(1)
        actions.addWidget(self.clear_button)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self.play_button.clicked.connect(self._play_selected)
        self.next_button.clicked.connect(self._play_selected_next)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self.engine.clear_queue)
        self.list.itemDoubleClicked.connect(
            lambda _item: self._play_selected()
        )
        self.list.itemSelectionChanged.connect(self._selection_changed)
        self.list.order_changed.connect(self._order_changed)
        self.engine.queue_changed.connect(self.refresh)
        self.refresh(list(engine.queue.songs), engine.queue.current_index)
        geometry = self.settings.value("player/queue_dialog_geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        self.settings.setValue(
            "player/queue_dialog_geometry", self.saveGeometry()
        )
        super().closeEvent(event)

    def refresh(self, songs: list[Song], current_index: int) -> None:
        self._updating = True
        selected_ids = {
            int(item.data(Qt.ItemDataRole.UserRole))
            for item in self.list.selectedItems()
        }
        self.list.clear()
        self._songs_by_id = {id(song): song for song in songs}
        for index, song in enumerate(songs):
            artist = song.artist or song.album_artist
            title = song.title or song.path
            prefix = "▶ " if index == current_index else ""
            item = QListWidgetItem(
                f"{prefix}{index + 1:02d}. {title}"
                + (f" - {artist}" if artist else "")
            )
            item.setData(Qt.ItemDataRole.UserRole, id(song))
            item.setToolTip(str(song.path))
            self.list.addItem(item)
            if id(song) in selected_ids:
                item.setSelected(True)
            if index == current_index:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
        count = len(songs)
        self.summary_label.setText(
            f"{count} Titel · Titel per Drag-and-drop umsortieren"
            if count != 1
            else "1 Titel · Titel per Drag-and-drop umsortieren"
        )
        self.clear_button.setEnabled(bool(songs))
        self._updating = False
        self._selection_changed()

    def _selected_rows(self) -> list[int]:
        return sorted({self.list.row(item) for item in self.list.selectedItems()})

    def _selection_changed(self) -> None:
        rows = self._selected_rows()
        single = len(rows) == 1
        self.play_button.setEnabled(single)
        self.next_button.setEnabled(
            single and rows[0] != self.engine.queue.current_index
        )
        self.remove_button.setEnabled(bool(rows))

    def _play_selected(self) -> None:
        rows = self._selected_rows()
        if len(rows) == 1:
            self.engine.play_index(rows[0])

    def _play_selected_next(self) -> None:
        rows = self._selected_rows()
        if len(rows) == 1:
            self.engine.play_next(rows[0])

    def _remove_selected(self) -> None:
        self.engine.remove_queue_indices(self._selected_rows())

    def _order_changed(self) -> None:
        if self._updating:
            return
        songs = [
            self._songs_by_id[int(self.list.item(row).data(Qt.ItemDataRole.UserRole))]
            for row in range(self.list.count())
        ]
        self.engine.reorder_queue(songs)
