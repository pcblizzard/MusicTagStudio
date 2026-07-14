import sys

from PySide6.QtWidgets import QApplication

from .settings import load_settings
from .theme import apply_theme
from .ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    def refresh_automatic_theme():
        settings = load_settings()

        if settings.theme == "automatic":
            apply_theme(
                app,
                settings.theme,
            )

    settings = load_settings()
    apply_theme(app, settings.theme)

    app.styleHints().colorSchemeChanged.connect(
        refresh_automatic_theme
    )

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
