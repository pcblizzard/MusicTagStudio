import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .apple_music_dialog import AppleMusicResultsDialog
from .cover import load_cover
from .editor import save_song_metadata
from .providers.apple_music import (
    AppleMusicProviderError,
    search_song,
)
from .scanner import scan_folder
from .song import Song
from .theme import (
    BUTTON_CHANGED,
    BUTTON_NORMAL,
    INPUT_CHANGED,
    INPUT_NORMAL,
)


DEFAULT_MUSIC_FOLDER = (
    r"C:\Users\Michael\Music\Stieber Twins\Stieber Twins"
    r"\Stieber Twins - Fenster zum Hof"
)

COVER_SIZE = 280

COLUMN_TRACK = 0
COLUMN_TITLE = 1
COLUMN_ARTIST = 2
COLUMN_ALBUM = 3
COLUMN_DISC = 4
COLUMN_YEAR = 5
COLUMN_ISRC = 6
COLUMN_LABEL = 7
COLUMN_COPYRIGHT = 8
COLUMN_COMPOSER = 9
COLUMN_PATH = 10


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MusicTagStudio")
        self.resize(1500, 760)

        self.folder: str | None = DEFAULT_MUSIC_FOLDER
        self.current_cover: QPixmap | None = None
        self.songs: list[Song] = []

        self.current_row = -1
        self.original_values: dict[str, str] = {}
        self.loading_editor = False
        self.has_unsaved_changes = False

        self.create_ui()

    def create_ui(self):
        container = QWidget()
        container_layout = QVBoxLayout(container)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.folder_label = QLabel(f"Ordner: {self.folder}")
        self.folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.select_button = QPushButton("Musikordner auswählen")
        self.select_button.clicked.connect(self.select_folder)

        self.scan_button = QPushButton("FLAC-Dateien scannen")
        self.scan_button.clicked.connect(self.scan_music)

        self.apple_search_button = QPushButton(
            "Ausgewählten Titel bei Apple Music suchen"
        )
        self.apple_search_button.clicked.connect(
            self.search_current_song_on_apple
        )
        self.apple_search_button.setEnabled(False)

        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels(
            [
                "Track",
                "Titel",
                "Künstler",
                "Album",
                "Disc",
                "Jahr",
                "ISRC",
                "Label",
                "Copyright",
                "Komponist",
                "Datei",
            ]
        )

        self.table.currentCellChanged.connect(
            self.load_current_song
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            COLUMN_TRACK,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            COLUMN_TITLE,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            COLUMN_ARTIST,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            COLUMN_ALBUM,
            QHeaderView.ResizeMode.Stretch,
        )

        for column in (
            COLUMN_DISC,
            COLUMN_YEAR,
            COLUMN_ISRC,
            COLUMN_LABEL,
            COLUMN_COPYRIGHT,
            COLUMN_COMPOSER,
        ):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        header.setSectionResizeMode(
            COLUMN_PATH,
            QHeaderView.ResizeMode.Interactive,
        )
        self.table.setColumnWidth(COLUMN_PATH, 240)

        left_layout.addWidget(self.folder_label)
        left_layout.addWidget(self.select_button)
        left_layout.addWidget(self.scan_button)
        left_layout.addWidget(self.apple_search_button)
        left_layout.addWidget(self.table)

        right_widget = QWidget()
        right_widget.setMinimumWidth(390)

        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)

        self.cover_label = QLabel("Kein Cover vorhanden")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setFixedSize(COVER_SIZE, COVER_SIZE)
        self.cover_label.setStyleSheet(
            """
            QLabel {
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 6px;
            }
            """
        )

        right_layout.addWidget(
            self.cover_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setVerticalSpacing(10)
        form_layout.setHorizontalSpacing(12)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.title_edit = QLineEdit()
        self.artist_edit = QLineEdit()
        self.album_artist_edit = QLineEdit()
        self.album_edit = QLineEdit()
        self.genre_edit = QLineEdit()
        self.year_edit = QLineEdit()
        self.track_edit = QLineEdit()
        self.total_tracks_edit = QLineEdit()
        self.disc_edit = QLineEdit()
        self.total_discs_edit = QLineEdit()
        self.isrc_edit = QLineEdit()
        self.label_edit = QLineEdit()
        self.copyright_edit = QLineEdit()
        self.composer_edit = QLineEdit()

        form_layout.addRow("Titel:", self.title_edit)
        form_layout.addRow("Künstler:", self.artist_edit)
        form_layout.addRow("Albumkünstler:", self.album_artist_edit)
        form_layout.addRow("Album:", self.album_edit)
        form_layout.addRow("Genre:", self.genre_edit)
        form_layout.addRow("Jahr:", self.year_edit)

        track_widget = QWidget()
        track_layout = QHBoxLayout(track_widget)
        track_layout.setContentsMargins(0, 0, 0, 0)
        track_layout.setSpacing(6)
        track_layout.addWidget(self.track_edit)
        track_layout.addWidget(QLabel("/"))
        track_layout.addWidget(self.total_tracks_edit)
        form_layout.addRow("Track:", track_widget)

        disc_widget = QWidget()
        disc_layout = QHBoxLayout(disc_widget)
        disc_layout.setContentsMargins(0, 0, 0, 0)
        disc_layout.setSpacing(6)
        disc_layout.addWidget(self.disc_edit)
        disc_layout.addWidget(QLabel("/"))
        disc_layout.addWidget(self.total_discs_edit)
        form_layout.addRow("Disc:", disc_widget)

        form_layout.addRow("ISRC:", self.isrc_edit)
        form_layout.addRow("Label:", self.label_edit)
        form_layout.addRow("Copyright:", self.copyright_edit)
        form_layout.addRow("Komponist:", self.composer_edit)

        self.save_button = QPushButton(BUTTON_NORMAL)
        self.save_button.clicked.connect(self.save_song)
        self.save_button.setEnabled(False)
        form_layout.addRow(self.save_button)

        right_layout.addWidget(form_widget)
        right_layout.addStretch()

        self.editor_fields = {
            "title": self.title_edit,
            "artist": self.artist_edit,
            "album_artist": self.album_artist_edit,
            "album": self.album_edit,
            "genre": self.genre_edit,
            "year": self.year_edit,
            "track": self.track_edit,
            "total_tracks": self.total_tracks_edit,
            "disc": self.disc_edit,
            "total_discs": self.total_discs_edit,
            "isrc": self.isrc_edit,
            "label": self.label_edit,
            "copyright": self.copyright_edit,
            "composer": self.composer_edit,
        }

        for field in self.editor_fields.values():
            field.textChanged.connect(self.update_dirty_state)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([1080, 420])
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)

        container_layout.addWidget(self.splitter)
        self.setCentralWidget(container)

        self.update_optional_columns()

    def select_folder(self):
        if not self.confirm_pending_changes():
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Musikordner auswählen",
            self.folder or "",
        )

        if folder:
            self.folder = folder
            self.folder_label.setText(f"Ordner: {folder}")

    def scan_music(self):
        if not self.confirm_pending_changes():
            return

        if not self.folder:
            QMessageBox.warning(
                self,
                "Fehler",
                "Bitte zuerst einen Ordner auswählen.",
            )
            return

        if not Path(self.folder).is_dir():
            QMessageBox.warning(
                self,
                "Ordner nicht gefunden",
                f"Der Musikordner wurde nicht gefunden:\n\n{self.folder}",
            )
            return

        try:
            self.songs = scan_folder(self.folder)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Scan fehlgeschlagen",
                f"Der Ordner konnte nicht gelesen werden:\n\n{error}",
            )
            return

        self.current_row = -1
        self.clear_editor()

        self.table.blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(len(self.songs))

        for row, song in enumerate(self.songs):
            self.update_table_row(row, song)

        self.table.blockSignals(False)
        self.update_optional_columns()

        if self.songs:
            self.table.setCurrentCell(0, 0)
            self.table.setFocus()

    def load_current_song(
        self,
        current_row: int,
        current_column: int,
        previous_row: int,
        previous_column: int,
    ):
        if current_row < 0 or current_row >= len(self.songs):
            self.apple_search_button.setEnabled(False)
            return

        if current_row == self.current_row:
            return

        if self.has_unsaved_changes:
            answer = self.ask_about_unsaved_changes()

            if answer == QMessageBox.StandardButton.Save:
                if not self.save_current_song(show_message=False):
                    self.restore_table_selection(self.current_row)
                    return
            elif answer == QMessageBox.StandardButton.Cancel:
                self.restore_table_selection(self.current_row)
                return

        self.display_song(current_row)

    def display_song(self, row: int):
        if row < 0 or row >= len(self.songs):
            return

        song = self.songs[row]
        self.current_row = row
        self.loading_editor = True

        values = self.song_to_values(song)

        for name, field in self.editor_fields.items():
            field.setText(values[name])

        self.original_values = values.copy()
        self.loading_editor = False
        self.update_dirty_state()
        self.apple_search_button.setEnabled(True)

        try:
            cover_data = load_cover(song.path)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Cover konnte nicht gelesen werden",
                str(error),
            )
            return

        self.show_cover(cover_data)

    def search_current_song_on_apple(self):
        if self.current_row < 0 or self.current_row >= len(self.songs):
            QMessageBox.warning(
                self,
                "Keine Datei ausgewählt",
                "Wähle zuerst einen Titel in der Tabelle aus.",
            )
            return

        if self.has_unsaved_changes:
            answer = QMessageBox.question(
                self,
                "Ungespeicherte Änderungen",
                (
                    "Im Editor befinden sich bereits ungespeicherte Änderungen.\n\n"
                    "Die Apple-Suche verwendet die aktuell sichtbaren Werte. "
                    "Möchtest du fortfahren?"
                ),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if answer != QMessageBox.StandardButton.Yes:
                return

        self.apple_search_button.setEnabled(False)
        self.apple_search_button.setText("Apple Music wird durchsucht …")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            results = search_song(
                title=self.title_edit.text(),
                artist=self.artist_edit.text(),
                album=self.album_edit.text(),
                country="DE",
            )
        except AppleMusicProviderError as error:
            QMessageBox.critical(
                self,
                "Apple-Suche fehlgeschlagen",
                str(error),
            )
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.apple_search_button.setText(
                "Ausgewählten Titel bei Apple Music suchen"
            )
            self.apple_search_button.setEnabled(True)

        if not results:
            QMessageBox.information(
                self,
                "Keine Treffer",
                "Für diesen Titel wurden keine Apple-Music-Treffer gefunden.",
            )
            return

        dialog = AppleMusicResultsDialog(results, self)

        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        result = dialog.selected_result

        if result is None:
            return

        self.apply_apple_result(result)

    def apply_apple_result(self, result):
        proposed_values = {
            "title": result.title,
            "artist": result.artist,
            "album_artist": result.album_artist,
            "album": result.album,
            "genre": result.genre,
            "year": result.year,
            "track": result.track,
            "total_tracks": result.total_tracks,
            "disc": result.disc,
            "total_discs": result.total_discs,
        }

        for name, value in proposed_values.items():
            if value:
                self.editor_fields[name].setText(value)

        self.update_dirty_state()

    def update_dirty_state(self):
        if self.loading_editor:
            return

        current_values = self.get_editor_values()

        for name, field in self.editor_fields.items():
            changed = (
                current_values.get(name, "")
                != self.original_values.get(name, "")
            )
            field.setStyleSheet(
                INPUT_CHANGED if changed else INPUT_NORMAL
            )

        self.has_unsaved_changes = (
            bool(self.original_values)
            and current_values != self.original_values
        )

        self.save_button.setEnabled(self.has_unsaved_changes)
        self.save_button.setText(
            BUTTON_CHANGED
            if self.has_unsaved_changes
            else BUTTON_NORMAL
        )

    def save_song(self):
        if self.save_current_song(show_message=True):
            self.table.setFocus()

    def save_current_song(self, show_message: bool) -> bool:
        row = self.current_row

        if row < 0 or row >= len(self.songs):
            if show_message:
                QMessageBox.warning(
                    self,
                    "Fehler",
                    "Keine Datei ausgewählt.",
                )
            return False

        current_song = self.songs[row]
        values = self.get_editor_values()

        updated_song = replace(
            current_song,
            **values,
        )

        try:
            save_song_metadata(updated_song.path, updated_song)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Speichern fehlgeschlagen",
                (
                    "Die Metadaten konnten nicht gespeichert werden:"
                    f"\n\n{error}"
                ),
            )
            return False

        self.songs[row] = updated_song
        self.update_table_row(row, updated_song)
        self.update_optional_columns()

        self.original_values = values.copy()
        self.update_dirty_state()

        if show_message:
            QMessageBox.information(
                self,
                "Gespeichert",
                "Metadaten wurden gespeichert.",
            )

        return True

    def update_optional_columns(self):
        optional_columns = {
            COLUMN_ISRC: any(song.isrc.strip() for song in self.songs),
            COLUMN_LABEL: any(song.label.strip() for song in self.songs),
            COLUMN_COPYRIGHT: any(
                song.copyright.strip()
                for song in self.songs
            ),
            COLUMN_COMPOSER: any(
                song.composer.strip()
                for song in self.songs
            ),
        }

        for column, has_values in optional_columns.items():
            self.table.setColumnHidden(column, not has_values)

    def confirm_pending_changes(self) -> bool:
        if not self.has_unsaved_changes:
            return True

        answer = self.ask_about_unsaved_changes()

        if answer == QMessageBox.StandardButton.Save:
            return self.save_current_song(show_message=False)

        if answer == QMessageBox.StandardButton.Discard:
            return True

        return False

    def ask_about_unsaved_changes(
        self,
    ) -> QMessageBox.StandardButton:
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Ungespeicherte Änderungen")
        message_box.setText(
            "Die Änderungen am aktuellen Titel wurden noch nicht gespeichert."
        )
        message_box.setInformativeText(
            "Möchtest du sie speichern, verwerfen oder beim aktuellen Titel bleiben?"
        )
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        message_box.setDefaultButton(
            QMessageBox.StandardButton.Save
        )

        save_button = message_box.button(
            QMessageBox.StandardButton.Save
        )
        discard_button = message_box.button(
            QMessageBox.StandardButton.Discard
        )
        cancel_button = message_box.button(
            QMessageBox.StandardButton.Cancel
        )

        if save_button is not None:
            save_button.setText("Speichern")
        if discard_button is not None:
            discard_button.setText("Verwerfen")
        if cancel_button is not None:
            cancel_button.setText("Abbrechen")

        return QMessageBox.StandardButton(message_box.exec())

    def restore_table_selection(self, row: int):
        if row < 0 or row >= len(self.songs):
            return

        self.table.blockSignals(True)
        self.table.setCurrentCell(row, 0)
        self.table.selectRow(row)
        self.table.blockSignals(False)
        self.table.setFocus()

    def get_editor_values(self) -> dict[str, str]:
        return {
            name: field.text()
            for name, field in self.editor_fields.items()
        }

    @staticmethod
    def song_to_values(song: Song) -> dict[str, str]:
        return {
            "title": song.title,
            "artist": song.artist,
            "album_artist": song.album_artist,
            "album": song.album,
            "genre": song.genre,
            "year": song.year,
            "track": song.track,
            "total_tracks": song.total_tracks,
            "disc": song.disc,
            "total_discs": song.total_discs,
            "isrc": song.isrc,
            "label": song.label,
            "copyright": song.copyright,
            "composer": song.composer,
        }

    def update_table_row(self, row: int, song: Song):
        track_text = song.track
        if song.total_tracks:
            track_text = f"{song.track}/{song.total_tracks}"

        disc_text = song.disc
        if song.total_discs:
            disc_text = f"{song.disc}/{song.total_discs}"

        values = [
            track_text,
            song.title,
            song.artist,
            song.album,
            disc_text,
            song.year,
            song.isrc,
            song.label,
            song.copyright,
            song.composer,
            song.path,
        ]

        for column, value in enumerate(values):
            self.table.setItem(
                row,
                column,
                QTableWidgetItem(value),
            )

    def show_cover(self, cover_data: bytes | None):
        if not cover_data:
            self.current_cover = None
            self.cover_label.clear()
            self.cover_label.setText("Kein Cover vorhanden")
            return

        pixmap = QPixmap()

        if not pixmap.loadFromData(cover_data):
            self.current_cover = None
            self.cover_label.clear()
            self.cover_label.setText(
                "Cover konnte nicht geladen werden"
            )
            return

        self.current_cover = pixmap

        scaled_cover = pixmap.scaled(
            self.cover_label.contentsRect().size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.cover_label.clear()
        self.cover_label.setPixmap(scaled_cover)

    def clear_editor(self):
        self.loading_editor = True

        for field in self.editor_fields.values():
            field.clear()
            field.setStyleSheet(INPUT_NORMAL)

        self.loading_editor = False
        self.original_values = {}
        self.has_unsaved_changes = False
        self.save_button.setEnabled(False)
        self.save_button.setText(BUTTON_NORMAL)
        self.apple_search_button.setEnabled(False)

        self.current_cover = None
        self.cover_label.clear()
        self.cover_label.setText("Kein Cover vorhanden")

    def closeEvent(self, event: QCloseEvent):
        if self.confirm_pending_changes():
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
