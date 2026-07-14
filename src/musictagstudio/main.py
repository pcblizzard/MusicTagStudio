import sys

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QMessageBox
)

from .editor import save_metadata

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QFileDialog,
    QLabel,
    QTableWidget,
    QTableWidgetItem
)

from .scanner import scan_folder


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("MusicTagStudio")
        self.resize(1000, 600)

        self.folder = None

        self.current_file = None

        self.create_ui()


    def create_ui(self):

        container = QWidget()
        layout = QVBoxLayout()

        self.folder_label = QLabel(
            "Kein Ordner ausgewählt"
        )

        self.select_button = QPushButton(
            "Musikordner auswählen"
        )

        self.select_button.clicked.connect(
            self.select_folder
        )

        self.scan_button = QPushButton(
            "FLAC-Dateien scannen"
        )

        self.scan_button.clicked.connect(
            self.scan_music
        )

        self.table = QTableWidget()

        self.table.setColumnCount(5)

        self.table.setHorizontalHeaderLabels(
            [
                "Titel",
                "Künstler",
                "Album",
                "Jahr",
                "Datei"
            ]
        )

        layout.addWidget(self.folder_label)
        layout.addWidget(self.select_button)
        layout.addWidget(self.scan_button)
        layout.addWidget(self.table)

        container.setLayout(layout)

        self.setCentralWidget(container)


    def select_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Musikordner auswählen"
        )

        if folder:
            self.folder = folder
            self.folder_label.setText(
                f"Ordner: {folder}"
            )


    def scan_music(self):

        if not self.folder:
            self.folder_label.setText(
                "Bitte zuerst einen Ordner auswählen!"
            )
            return


        songs = scan_folder(self.folder)

        self.table.setRowCount(
            len(songs)
        )


        for row, song in enumerate(songs):

            self.table.setItem(
                row,
                0,
                QTableWidgetItem(song["title"])
            )

            self.table.setItem(
                row,
                1,
                QTableWidgetItem(song["artist"])
            )

            self.table.setItem(
                row,
                2,
                QTableWidgetItem(song["album"])
            )

            self.table.setItem(
                row,
                3,
                QTableWidgetItem(song["year"])
            )

            self.table.setItem(
                row,
                4,
                QTableWidgetItem(song["path"])
            )


if __name__ == "__main__":

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())