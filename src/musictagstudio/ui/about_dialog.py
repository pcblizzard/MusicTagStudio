from __future__ import annotations

import platform
import ssl
import sys
from pathlib import Path

import PySide6
from PySide6.QtCore import QLibraryInfo, QSettings, qVersion
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
)

from .. import __version__
from ..diagnostics import project_root
from ..i18n import tr
from ..settings import load_settings


PUBLIC_INTERFACES = (
    "MusicBrainz Web Service",
    "Cover Art Archive",
    "Discogs API",
    "Apple Music-Webseiten und iTunes Search API",
    "TIDAL API",
    "Spotify Web API",
    "Genius API",
    "LRCLIB API",
    "TheAudioDB API",
    "Deezer API",
)


class AboutDialog(QDialog):
    def __init__(self, parent=None, *, language: str = "automatic") -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(tr("about_window_title", language))
        self.resize(660, 570)

        layout = QVBoxLayout(self)
        heading = QLabel(f"<h1>MusicTagStudio {__version__}</h1>")
        layout.addWidget(heading)

        self.tabs = QTabWidget()
        self.about_browser = _browser(about_html(language))
        self.contributors_browser = _browser(contributors_html(language))
        self.debug_browser = _browser(f"<pre>{_escape_html(debug_information())}</pre>")
        self.tabs.addTab(self.about_browser, tr("tab_about", language))
        self.tabs.addTab(self.contributors_browser, tr("tab_contributors", language))
        self.tabs.addTab(self.debug_browser, tr("tab_debug", language))
        layout.addWidget(self.tabs, 1)

        button_row = QHBoxLayout()
        self.copy_button = QPushButton(tr("copy_debug", language))
        self.copy_button.clicked.connect(self.copy_debug_information)
        button_row.addWidget(self.copy_button)
        button_row.addStretch(1)
        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        button_row.addWidget(close_buttons)
        layout.addLayout(button_row)

    def copy_debug_information(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(debug_information())
        self.copy_button.setText(tr("copy_debug_done", self.language))


def about_html(language: str = "automatic") -> str:
    interfaces = "".join(f"<li>{item}</li>" for item in PUBLIC_INTERFACES)
    return tr(
        "about_intro_html",
        language,
        version=__version__,
        license=_license_description(),
        interfaces=interfaces,
    )


def contributors_html(language: str = "automatic") -> str:
    return tr("contributors_html", language)


def debug_information() -> str:
    windows_version = platform.win32_ver()
    os_text = " ".join(value for value in windows_version[:2] if value)
    if not os_text:
        os_text = platform.platform()
    qt_library_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.LibrariesPath)
    provider_lines = _provider_debug_lines()
    return "\n".join(
        (
            f"MusicTagStudio - Version {__version__}",
            f"Revision: {_git_revision()}",
            "",
            f"Python {platform.python_version()}",
            f"PySide6 {PySide6.__version__}",
            f"Qt {qVersion()}",
            "Diagnoseprotokollierung ist aktiviert.",
            "",
            f"Betriebssystem: {os_text}",
            f"CPU-Architektur: {platform.machine() or 'Unbekannt'}",
            f"Kernel: {platform.system().casefold()} {platform.release()} "
            f"{platform.version()}",
            "",
            "Aktivierte Komponenten:",
            "- Lokaler Metadaten-Editor",
            "- Medienbibliothek",
            "- Lokaler Audioplayer",
            "- Audio-Analyse",
            "- Bibliotheksprüfung",
            "- Lyrics und Karaoke-Anzeige",
            "- Online-Katalogabgleich",
            "",
            "Konfigurierte Online-Anbieter:",
            *provider_lines,
            "",
            f"Streaming-Cache: {_streaming_cache_status()}",
            "",
            "Kryptographische Bibliothek:",
            f"- {ssl.OPENSSL_VERSION}",
            "",
            f"Qt-Bibliothekspfad: {qt_library_path}",
            f"Python-Executable: {sys.executable}",
        )
    )


def _provider_debug_lines() -> tuple[str, ...]:
    settings = load_settings()
    ui_settings = QSettings("MusicTagStudio", "MusicTagStudio")
    tidal_scope = str(ui_settings.value("provider_diagnostics/TIDAL/scope", "")).strip()
    genius_configured = bool(
        ui_settings.value(
            "provider_diagnostics/Genius/configured",
            False,
            type=bool,
        )
    )
    return (
        f"- Discogs: {'eingerichtet' if settings.discogs_token else 'nicht eingerichtet'}",
        (
            "- TIDAL: "
            + ("eingerichtet" if settings.tidal_client_id else "nicht eingerichtet")
            + (f" · Scope: {tidal_scope}" if tidal_scope else "")
        ),
        (
            "- Spotify: "
            + ("eingerichtet" if settings.spotify_client_id else "nicht eingerichtet")
        ),
        (
            "- Genius: "
            + ("eingerichtet" if genius_configured else "nicht eingerichtet")
        ),
        (
            "- Anfrageabstand: "
            f"Apple {settings.apple_request_interval_seconds:.1f} s · "
            f"Genius {settings.genius_request_interval_seconds:.1f} s"
        ),
    )


def _streaming_cache_status() -> str:
    path = project_root() / "cache" / "media_library" / "streaming_availability.sqlite3"
    try:
        size = path.stat().st_size
    except OSError:
        return "noch nicht angelegt"
    return f"vorhanden · {size / 1024:.1f} KiB"


def _license_description() -> str:
    license_path = project_root() / "LICENSE"
    try:
        content = license_path.read_text(encoding="utf-8").strip()
    except OSError:
        content = ""
    if not content:
        return "Keine Lizenz festgelegt (LICENSE ist leer)"
    first_line = next(
        (line.strip() for line in content.splitlines() if line.strip()), ""
    )
    return first_line or "Lizenztext in LICENSE"


def _git_revision() -> str:
    git_dir = project_root() / ".git"
    head_path = git_dir / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref_path = git_dir / Path(head.removeprefix("ref:").strip())
            revision = ref_path.read_text(encoding="utf-8").strip()
        else:
            revision = head
    except OSError:
        return "Nicht verfügbar"
    return revision[:12] if revision else "Nicht verfügbar"


def _browser(html: str) -> QTextBrowser:
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setHtml(html)
    return browser


def _escape_html(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
