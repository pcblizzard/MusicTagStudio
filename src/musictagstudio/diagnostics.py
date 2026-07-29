from __future__ import annotations

import logging
import os
import platform
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path


_LOGGERS: dict[str, logging.Logger] = {}
_SESSION_ID = (
    datetime.now().strftime("%Y%m%d-%H%M%S")
    + "-"
    + uuid.uuid4().hex[:8]
)
_EXCEPTION_HOOK_INSTALLED = False


def is_frozen() -> bool:
    """True, wenn die App als gebündeltes Exe (PyInstaller) läuft."""
    return bool(getattr(sys, "frozen", False))


def _portable_data_root() -> Path | None:
    """Ordner für portablen Datenmodus oder None (Standardmodus).

    Legt der Installer neben die Exe eine Markierungsdatei ``portable.flag``,
    werden die Nutzerdaten in ``<Exe-Ordner>\\data`` gehalten statt in
    %LOCALAPPDATA%. Nur im gebündelten Betrieb relevant.
    """
    if not is_frozen():
        return None
    exe_dir = Path(sys.executable).resolve().parent
    if (exe_dir / "portable.flag").is_file():
        return exe_dir / "data"
    return None


def user_data_dir() -> Path:
    """Beschreibbarer Ablageort für Konfiguration, Logs, Cache (installiert).

    Standard: %LOCALAPPDATA%\\MusicTagStudio (bzw. %APPDATA%), damit die
    installierte App auch unter schreibgeschütztem Programme-Ordner
    funktioniert und Nutzerdaten ein Update überleben. Im portablen Modus
    (Markierungsdatei neben der Exe) liegen die Daten im Installationsordner.
    """
    portable = _portable_data_root()
    if portable is not None:
        root = portable
    else:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = (
            Path(base) / "MusicTagStudio" if base else Path.home() / ".musictagstudio"
        )
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_root() -> Path:
    """
    Ermittelt den Ablageort für Nutzerdaten (Konfiguration, Logs, Cache).

    Als installierte Exe (frozen) gibt es kein Repository -> ein
    beschreibbarer, benutzereigener Ordner wird verwendet. Im Entwicklungs-
    und Testbetrieb wird vom Arbeitsverzeichnis nach einer pyproject.toml
    gesucht; wird keine gefunden, bleibt das Arbeitsverzeichnis der Ablageort.
    """
    if is_frozen():
        return user_data_dir()

    cwd = Path.cwd().resolve()

    for parent in (
        cwd,
        *cwd.parents,
    ):
        if (
            parent
            / "pyproject.toml"
        ).is_file():
            return parent

    return cwd

def resource_root() -> Path:
    """Read-only-Ablageort für mitgelieferte Ressourcen (frozen: Bundle).

    Als installierte Exe liegen gebündelte Dateien (locales, assets, tools)
    im PyInstaller-Bundle (sys._MEIPASS); im Entwicklungsbetrieb im
    Repository-Wurzelverzeichnis.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    # Repository-Wurzel (…/src/musictagstudio/diagnostics.py -> parents[2]).
    return Path(__file__).resolve().parents[2]


def log_directory() -> Path:
    path = (
        project_root()
        / "logs"
    )
    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def cache_directory() -> Path:
    path = (
        project_root()
        / "cache"
    )
    path.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def current_session_id() -> str:
    return _SESSION_ID


class _SessionFilter(
    logging.Filter
):
    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:
        record.session_id = (
            _SESSION_ID
        )

        return True


def get_diagnostic_logger(
    name: str,
) -> logging.Logger:
    existing = _LOGGERS.get(name)

    if existing is not None:
        return existing

    logger = logging.getLogger(
        f"musictagstudio.{name}"
    )
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    expected_path = (
        log_directory()
        / f"{name}.log"
    ).resolve()

    for existing_handler in list(
        logger.handlers
    ):
        existing_filename = getattr(
            existing_handler,
            "baseFilename",
            "",
        )

        if (
            not existing_filename
            or Path(
                existing_filename
            ).resolve()
            != expected_path
        ):
            logger.removeHandler(
                existing_handler
            )
            existing_handler.close()

    if not logger.handlers:
        handler = logging.FileHandler(
            expected_path,
            encoding="utf-8",
        )
        handler.addFilter(
            _SessionFilter()
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | "
                "session=%(session_id)s | %(message)s"
            )
        )
        logger.addHandler(handler)

    _LOGGERS[name] = logger

    return logger


def install_global_exception_logging() -> None:
    global _EXCEPTION_HOOK_INSTALLED

    if _EXCEPTION_HOOK_INSTALLED:
        return

    _EXCEPTION_HOOK_INSTALLED = True
    logger = get_diagnostic_logger(
        "application"
    )
    previous_hook = sys.excepthook

    def exception_hook(
        exception_type,
        exception,
        traceback_object,
    ):
        logger.critical(
            "Unbehandelte Ausnahme",
            exc_info=(
                exception_type,
                exception,
                traceback_object,
            ),
        )

        if (
            previous_hook
            is not None
            and previous_hook
            is not exception_hook
        ):
            previous_hook(
                exception_type,
                exception,
                traceback_object,
            )

    sys.excepthook = (
        exception_hook
    )

    if hasattr(
        threading,
        "excepthook",
    ):
        previous_thread_hook = (
            threading.excepthook
        )

        def thread_exception_hook(
            args,
        ):
            logger.critical(
                "Unbehandelte Thread-Ausnahme | Thread=%s",
                getattr(
                    args.thread,
                    "name",
                    "?",
                ),
                exc_info=(
                    args.exc_type,
                    args.exc_value,
                    args.exc_traceback,
                ),
            )

            if (
                previous_thread_hook
                is not None
                and previous_thread_hook
                is not thread_exception_hook
            ):
                previous_thread_hook(
                    args
                )

        threading.excepthook = (
            thread_exception_hook
        )


def log_application_start(
    *,
    version: str,
) -> None:
    logger = get_diagnostic_logger(
        "application"
    )
    logger.info(
        "PROGRAMMSTART | Version=%s | Session=%s",
        version,
        _SESSION_ID,
    )
    logger.info(
        "Umgebung | Python=%s | Implementierung=%s | "
        "Betriebssystem=%s | Architektur=%s",
        platform.python_version(),
        platform.python_implementation(),
        platform.platform(),
        platform.machine(),
    )
    logger.info(
        "Pfade | executable=%s | cwd=%s | project_root=%s | "
        "logs=%s | cache=%s | module=%s",
        sys.executable,
        Path.cwd().resolve(),
        project_root(),
        log_directory(),
        cache_directory(),
        Path(__file__).resolve(),
    )
    logger.info(
        "Argumente | %r",
        sys.argv,
    )
    logger.info(
        "Prozess | pid=%s | parent_pid=%s",
        os.getpid(),
        os.getppid(),
    )


def log_application_stop(
    exit_code: int,
) -> None:
    get_diagnostic_logger(
        "application"
    ).info(
        "PROGRAMMENDE | Exit-Code=%s",
        exit_code,
    )
