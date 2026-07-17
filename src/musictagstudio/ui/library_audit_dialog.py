from __future__ import annotations

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Signal,
    Slot,
    Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..library_audit.checker import (
    audit_library,
)
from ..library_audit.models import (
    LibraryAuditSummary,
)
from ..models.song import Song


ERROR_COLOR = QColor(
    105,
    42,
    42,
)
WARNING_COLOR = QColor(
    95,
    76,
    35,
)
INFO_COLOR = QColor(
    42,
    69,
    92,
)
GOOD_COLOR = QColor(
    41,
    83,
    54,
)


class AuditSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class AuditWorker(QRunnable):
    def __init__(
        self,
        songs: list[Song],
    ):
        super().__init__()
        self.songs = songs
        self.signals = AuditSignals()

    @Slot()
    def run(self):
        try:
            result = audit_library(
                self.songs
            )
        except Exception as error:
            self.signals.failed.emit(
                str(error)
            )
            return

        self.signals.finished.emit(result)


class LibraryAuditDialog(QDialog):
    def __init__(
        self,
        selected_songs: list[Song],
        all_songs: list[Song],
        parent=None,
        *,
        embedded: bool = False,
    ):
        super().__init__(parent)

        self.embedded = embedded
        self.selected_songs = selected_songs
        self.all_songs = all_songs
        self.summary: (
            LibraryAuditSummary | None
        ) = None
        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        if not self.embedded:
            self.setWindowTitle(
                "Bibliotheksprüfung"
            )
            self.resize(
                1350,
                760,
            )
        else:
            self.setWindowFlags(
                Qt.WindowType.Widget
            )

        layout = QVBoxLayout(self)

        self.status_label = QLabel(
            "Noch keine Prüfung durchgeführt."
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(
            self.status_label
        )

        self.filter_combo = QComboBox()
        self.filter_combo.addItem(
            "Alle Hinweise",
            "all",
        )
        self.filter_combo.addItem(
            "Nur Fehler",
            "error",
        )
        self.filter_combo.addItem(
            "Nur Warnungen",
            "warning",
        )
        self.filter_combo.addItem(
            "Nur Informationen",
            "info",
        )
        self.filter_combo.currentIndexChanged.connect(
            self.refresh_table
        )
        layout.addWidget(
            self.filter_combo
        )

        self.selected_button = QPushButton(
            (
                "Markierte Titel prüfen "
                f"({len(selected_songs)})"
            )
        )
        self.selected_button.clicked.connect(
            lambda:
            self.start_audit(
                self.selected_songs
            )
        )
        self.selected_button.setEnabled(
            bool(selected_songs)
        )
        layout.addWidget(
            self.selected_button
        )

        self.all_button = QPushButton(
            (
                "Alle gescannten Titel prüfen "
                f"({len(all_songs)})"
            )
        )
        self.all_button.clicked.connect(
            lambda:
            self.start_audit(
                self.all_songs
            )
        )
        self.all_button.setEnabled(
            bool(all_songs)
        )
        layout.addWidget(
            self.all_button
        )

        splitter = QSplitter()

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Stufe",
                "Kategorie",
                "Album",
                "Titel",
                "Meldung",
                "Datei",
                "Details",
            ]
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.itemSelectionChanged.connect(
            self.show_selected_details
        )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )

        for column in (
            0,
            1,
            2,
            3,
            5,
            6,
        ):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        details_widget = QWidget()
        details_layout = QVBoxLayout(
            details_widget
        )
        details_layout.addWidget(
            QLabel("Details")
        )
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        details_layout.addWidget(
            self.details
        )

        splitter.addWidget(
            self.table
        )
        splitter.addWidget(
            details_widget
        )
        splitter.setSizes(
            [1000, 350]
        )

        layout.addWidget(
            splitter
        )

        self.close_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons = self.close_buttons
        buttons.rejected.connect(
            self.reject
        )
        layout.addWidget(
            buttons
        )

    def set_songs(
        self,
        selected_songs: list[Song],
        all_songs: list[Song],
    ) -> None:
        self.selected_songs = list(selected_songs)
        self.all_songs = list(all_songs)
        self.selected_button.setText(
            "Markierte Titel prüfen "
            f"({len(self.selected_songs)})"
        )
        self.selected_button.setEnabled(
            bool(self.selected_songs)
        )
        self.all_button.setText(
            "Alle gescannten Titel prüfen "
            f"({len(self.all_songs)})"
        )
        self.all_button.setEnabled(
            bool(self.all_songs)
        )

    def start_audit(
        self,
        songs: list[Song],
    ):
        if not songs:
            return

        self.status_label.setText(
            "Bibliothek wird geprüft …"
        )
        self.table.setRowCount(0)
        self.details.clear()

        worker = AuditWorker(songs)
        worker.signals.finished.connect(
            self.audit_finished
        )
        worker.signals.failed.connect(
            self.audit_failed
        )
        self.thread_pool.start(worker)

    def audit_finished(
        self,
        summary: LibraryAuditSummary,
    ):
        self.summary = summary
        self.status_label.setText(
            (
                f"{summary.checked_files} Dateien · "
                f"{summary.checked_albums} Alben · "
                f"{summary.error_count} Fehler · "
                f"{summary.warning_count} Warnungen · "
                f"{summary.info_count} Informationen · "
                f"Gesundheit {summary.health_score}/100"
            )
        )
        self.refresh_table()

    def audit_failed(
        self,
        message: str,
    ):
        self.status_label.setText(
            "Prüfung fehlgeschlagen: "
            + message
        )

    def refresh_table(self):
        if self.summary is None:
            return

        severity_filter = (
            self.filter_combo.currentData()
        )
        issues = [
            issue
            for issue in self.summary.issues
            if (
                severity_filter == "all"
                or issue.severity
                == severity_filter
            )
        ]

        self.table.setRowCount(
            len(issues)
        )

        for row, issue in enumerate(
            issues
        ):
            values = [
                severity_label(
                    issue.severity
                ),
                issue.category,
                issue.album_display,
                issue.title,
                issue.message,
                issue.path,
                (
                    "Vorhanden"
                    if issue.details
                    else ""
                ),
            ]

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    value
                )
                item.setData(
                    32,
                    issue.details,
                )
                item.setBackground(
                    severity_color(
                        issue.severity
                    )
                )
                self.table.setItem(
                    row,
                    column,
                    item,
                )

    def show_selected_details(self):
        items = self.table.selectedItems()

        if not items:
            self.details.clear()
            return

        details = items[0].data(32)
        self.details.setPlainText(
            details or "Keine weiteren Details."
        )


def severity_label(
    severity: str,
) -> str:
    return {
        "error": "Fehler",
        "warning": "Warnung",
        "info": "Info",
    }.get(
        severity,
        severity,
    )


def severity_color(
    severity: str,
) -> QColor:
    return {
        "error": ERROR_COLOR,
        "warning": WARNING_COLOR,
        "info": INFO_COLOR,
    }.get(
        severity,
        GOOD_COLOR,
    )
