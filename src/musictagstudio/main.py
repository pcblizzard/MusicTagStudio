import sys

from PySide6.QtCore import (
    qInstallMessageHandler,
    Qt,
)
from PySide6.QtWidgets import QApplication

from . import __version__
from .diagnostics import (
    get_diagnostic_logger,
    install_global_exception_logging,
    log_application_start,
    log_application_stop,
)
from .settings import apply_request_intervals, load_settings
from .theme import apply_theme
from .ui.main_window import MainWindow


def _install_qt_logging() -> None:
    logger = get_diagnostic_logger("qt")

    def qt_message_handler(
        message_type,
        context,
        message,
    ):
        logger.warning(
            "Qt | Typ=%s | Datei=%s | Zeile=%s | Funktion=%s | %s",
            message_type,
            getattr(
                context,
                "file",
                "",
            ),
            getattr(
                context,
                "line",
                "",
            ),
            getattr(
                context,
                "function",
                "",
            ),
            message,
        )

    qInstallMessageHandler(qt_message_handler)


def main():
    install_global_exception_logging()
    log_application_start(
        version=__version__,
    )
    _install_qt_logging()
    logger = get_diagnostic_logger("application")

    try:
        logger.info("QApplication wird erstellt")
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)

        def refresh_automatic_theme():
            settings = load_settings()
            logger.info(
                "Automatisches Theme aktualisiert | Theme=%s",
                settings.theme,
            )

            if settings.theme == "automatic":
                apply_theme(
                    app,
                    settings.theme,
                    settings.theme_style,
                )

        logger.info("Einstellungen werden geladen")
        settings = load_settings()
        apply_request_intervals(settings)
        logger.info(
            "Einstellungen geladen | Theme=%s | "
            "Metadatenquelle=%s | Apple-Store=%s | "
            "Fehlende Felder ergänzen=%s",
            settings.theme,
            settings.selected_provider,
            settings.apple_country,
            settings.enrich_missing_fields,
        )
        apply_theme(
            app,
            settings.theme,
            settings.theme_style,
        )
        logger.info("Theme angewendet")

        app.styleHints().colorSchemeChanged.connect(refresh_automatic_theme)

        logger.info("Hauptfenster wird erstellt")
        window = MainWindow()
        window.show()
        logger.info(
            "Hauptfenster sichtbar | Klasse=%s | Modul=%s",
            type(window).__name__,
            type(window).__module__,
        )

        exit_code = app.exec()
        log_application_stop(exit_code)

        return exit_code
    except Exception:
        logger.exception("Programmstart oder Hauptschleife fehlgeschlagen")
        raise


if __name__ == "__main__":
    sys.exit(main())
