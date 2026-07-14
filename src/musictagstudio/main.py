import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
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

from .cover import load_cover
from .editor import save_song_metadata
from .scanner import scan_folder
from .song import Song


DEFAULT_MUSIC_FOLDER = (
    r"C:\Users\Michael\Music\Stieber Twins\Stieber Twins"
    r"\Stieber Twins - Fenster zum Hof"
)

COVER_SIZE = 280


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MusicTagStudio")
        self.resize(1280, 720)

        self.folder: str | None = DEFAULT_MUSIC_FOLDER
        self.current_cover: QPixmap | None = None
        self.songs: list[Song] = []

        self.create_ui()

    def create_ui(self):
        container = QWidget()
        container_layout = QVBoxLayout(container)

        # Linke Seite: Ordnerauswahl und Dateiliste

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

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Track",
                "Titel",
                "Künstler",
                "Album",
                "Disc",
                "Jahr",
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
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            6,
            QHeaderView.ResizeMode.Interactive,
        )

        self.table.setColumnWidth(6, 240)

        left_layout.addWidget(self.folder_label)
        left_layout.addWidget(self.select_button)
        left_layout.addWidget(self.scan_button)
        left_layout.addWidget(self.table)

        # Rechte Seite: Cover und Tag-Editor

        right_widget = QWidget()
        right_widget.setMinimumWidth(360)

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

        form_layout.addRow("Titel:", self.title_edit)
        form_layout.addRow("Künstler:", self.artist_edit)
        form_layout.addRow(
            "Albumkünstler:",
            self.album_artist_edit,
        )
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

        self.save_button = QPushButton("Änderungen speichern")
        self.save_button.clicked.connect(self.save_song)

        form_layout.addRow(self.save_button)

        right_layout.addWidget(form_widget)
        right_layout.addStretch()

        # Verschiebbare Trennlinie

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)

        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([900, 380])

        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)

        container_layout.addWidget(self.splitter)

        self.setCentralWidget(container)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Musikordner auswählen",
            self.folder or "",
        )

        if folder:
            self.folder = folder
            self.folder_label.setText(f"Ordner: {folder}")

    def scan_music(self):
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

        self.clear_editor()

        self.table.clearContents()
        self.table.setRowCount(len(self.songs))

        for row, song in enumerate(self.songs):
            self.update_table_row(row, song)

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
            return

        song = self.songs[current_row]

        self.title_edit.setText(song.title)
        self.artist_edit.setText(song.artist)
        self.album_artist_edit.setText(song.album_artist)
        self.album_edit.setText(song.album)
        self.genre_edit.setText(song.genre)
        self.year_edit.setText(song.year)

        self.track_edit.setText(song.track)
        self.total_tracks_edit.setText(song.total_tracks)

        self.disc_edit.setText(song.disc)
        self.total_discs_edit.setText(song.total_discs)

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

    def save_song(self):
        row = self.table.currentRow()

        if row < 0 or row >= len(self.songs):
            QMessageBox.warning(
                self,
                "Fehler",
                "Keine Datei ausgewählt.",
            )
            return

        song = self.songs[row]

        song.title = self.title_edit.text()
        song.artist = self.artist_edit.text()
        song.album_artist = self.album_artist_edit.text()
        song.album = self.album_edit.text()
        song.genre = self.genre_edit.text()
        song.year = self.year_edit.text()

        song.track = self.track_edit.text()
        song.total_tracks = self.total_tracks_edit.text()

        song.disc = self.disc_edit.text()
        song.total_discs = self.total_discs_edit.text()

        try:
            save_song_metadata(song.path, song)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Speichern fehlgeschlagen",
                (
                    "Die Metadaten konnten nicht gespeichert werden:"
                    f"\n\n{error}"
                ),
            )
            return

        self.update_table_row(row, song)

        QMessageBox.information(
            self,
            "Gespeichert",
            "Metadaten wurden gespeichert.",
        )

        self.table.setFocus()

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
        self.title_edit.clear()
        self.artist_edit.clear()
        self.album_artist_edit.clear()
        self.album_edit.clear()
        self.genre_edit.clear()
        self.year_edit.clear()

        self.track_edit.clear()
        self.total_tracks_edit.clear()

        self.disc_edit.clear()
        self.total_discs_edit.clear()

        self.current_cover = None
        self.cover_label.clear()
        self.cover_label.setText("Kein Cover vorhanden")


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()