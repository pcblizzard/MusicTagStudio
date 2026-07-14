import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
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
from .editor import save_metadata
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
        self.resize(1200, 680)

        self.folder: str | None = DEFAULT_MUSIC_FOLDER
        self.current_file: str | None = None
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
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            [
                "Titel",
                "Künstler",
                "Album",
                "Jahr",
                "Datei",
            ]
        )

        self.table.cellClicked.connect(self.load_song)

        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
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
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Interactive,
        )

        self.table.setColumnWidth(4, 240)

        left_layout.addWidget(self.folder_label)
        left_layout.addWidget(self.select_button)
        left_layout.addWidget(self.scan_button)
        left_layout.addWidget(self.table)

        # Rechte Seite: Cover und Tag-Editor

        right_widget = QWidget()
        right_widget.setMinimumWidth(320)

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
        self.album_edit = QLineEdit()
        self.year_edit = QLineEdit()

        for field in (
            self.title_edit,
            self.artist_edit,
            self.album_edit,
            self.year_edit,
        ):
            field.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

        form_layout.addRow("Titel:", self.title_edit)
        form_layout.addRow("Künstler:", self.artist_edit)
        form_layout.addRow("Album:", self.album_edit)
        form_layout.addRow("Jahr:", self.year_edit)

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
        self.splitter.setSizes([850, 350])

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

        self.current_file = None
        self.current_cover = None

        self.clear_editor()

        self.table.clearContents()
        self.table.setRowCount(len(self.songs))

        for row, song in enumerate(self.songs):
            self.table.setItem(
                row,
                0,
                QTableWidgetItem(song.title),
            )
            self.table.setItem(
                row,
                1,
                QTableWidgetItem(song.artist),
            )
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(song.album),
            )
            self.table.setItem(
                row,
                3,
                QTableWidgetItem(song.year),
            )
            self.table.setItem(
                row,
                4,
                QTableWidgetItem(song.path),
            )

    def load_song(self, row: int, column: int):
        if row < 0 or row >= len(self.songs):
            return

        song = self.songs[row]
        self.current_file = song.path

        self.title_edit.setText(song.title)
        self.artist_edit.setText(song.artist)
        self.album_edit.setText(song.album)
        self.year_edit.setText(song.year)

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
        self.update_cover_display()

    def update_cover_display(self):
        if self.current_cover is None:
            return

        available_size = self.cover_label.contentsRect().size()

        scaled_cover = self.current_cover.scaled(
            available_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.cover_label.clear()
        self.cover_label.setPixmap(scaled_cover)

    def clear_editor(self):
        self.title_edit.clear()
        self.artist_edit.clear()
        self.album_edit.clear()
        self.year_edit.clear()

        self.current_cover = None
        self.cover_label.clear()
        self.cover_label.setText("Kein Cover vorhanden")

    def save_song(self):
        row = self.table.currentRow()

        if (
            self.current_file is None
            or row < 0
            or row >= len(self.songs)
        ):
            QMessageBox.warning(
                self,
                "Fehler",
                "Keine Datei ausgewählt.",
            )
            return

        title = self.title_edit.text()
        artist = self.artist_edit.text()
        album = self.album_edit.text()
        year = self.year_edit.text()

        try:
            save_metadata(
                self.current_file,
                title,
                artist,
                album,
                year,
            )
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

        # Auch das Song-Objekt im Arbeitsspeicher aktualisieren.
        song = self.songs[row]

        song.title = title
        song.artist = artist
        song.album = album
        song.year = year

        self.table.setItem(
            row,
            0,
            QTableWidgetItem(song.title),
        )
        self.table.setItem(
            row,
            1,
            QTableWidgetItem(song.artist),
        )
        self.table.setItem(
            row,
            2,
            QTableWidgetItem(song.album),
        )
        self.table.setItem(
            row,
            3,
            QTableWidgetItem(song.year),
        )

        QMessageBox.information(
            self,
            "Gespeichert",
            "Metadaten wurden gespeichert.",
        )


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()