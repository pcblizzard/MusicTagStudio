from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..i18n import tr
from ..providers import tidal_exact


class _LoginWorker(QObject):
    ready = Signal(str, str)  # verification_uri, user_code
    done = Signal(bool)

    @Slot()
    def run(self) -> None:
        try:
            session = tidal_exact.new_session()
            login, future = tidal_exact.start_device_login(session)
        except Exception:  # noqa: BLE001
            self.done.emit(False)
            return
        uri = str(
            getattr(login, "verification_uri_complete", "")
            or getattr(login, "verification_uri", "")
        )
        if uri and not uri.startswith("http"):
            uri = "https://" + uri
        self.ready.emit(uri, str(getattr(login, "user_code", "")))
        try:
            future.result()
            tidal_exact.save_credentials(tidal_exact.session_credentials(session))
            self.done.emit(True)
        except Exception:  # noqa: BLE001
            self.done.emit(False)


class TidalConnectDialog(QDialog):
    """Verbindet ein TIDAL-Konto per Geräte-Login (opt-in, inoffizielle API)."""

    connected = Signal()

    def __init__(self, parent=None, *, language: str = "automatic") -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(tr("tidal_connect_title", language))
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        self.intro = QLabel(tr("tidal_connect_intro", language))
        self.intro.setWordWrap(True)
        layout.addWidget(self.intro)

        self.link_label = QLabel("…")
        self.link_label.setWordWrap(True)
        self.link_label.setTextInteractionFlags(
            self.link_label.textInteractionFlags().TextSelectableByMouse
        )
        layout.addWidget(self.link_label)

        self.open_button = QPushButton(tr("tidal_connect_open", language))
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_link)
        layout.addWidget(self.open_button)

        self.status = QLabel(tr("tidal_connect_starting", language))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.close_button = QPushButton(tr("close_btn", language))
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self._uri = ""
        self._thread = QThread(self)
        self._worker = _LoginWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.ready.connect(self._on_ready)
        self._worker.done.connect(self._on_done)
        self._worker.done.connect(self._thread.quit)
        self._thread.start()

    @Slot(str, str)
    def _on_ready(self, uri: str, code: str) -> None:
        self._uri = uri
        self.link_label.setText(
            tr("tidal_connect_link", self.language, uri=uri, code=code)
        )
        self.open_button.setEnabled(bool(uri))
        self.status.setText(tr("tidal_connect_waiting", self.language))

    @Slot(bool)
    def _on_done(self, success: bool) -> None:
        if success:
            self.status.setText(tr("tidal_connect_success", self.language))
            self.connected.emit()
        else:
            self.status.setText(tr("tidal_connect_failed", self.language))

    def _open_link(self) -> None:
        if self._uri:
            QDesktopServices.openUrl(QUrl(self._uri))
