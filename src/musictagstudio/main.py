import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from scanner import scan_music_folder


class MusicTagStudio(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MusicTagStudio")
        self.resize(900, 600)

        files = scan_music_folder(r"C:\Users\Michael\Music")

        label = QLabel(
            f"Gefundene FLAC-Dateien: {len(files)}"
        )

        self.setCentralWidget(label)


def main():
    app = QApplication(sys.argv)

    window = MusicTagStudio()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()