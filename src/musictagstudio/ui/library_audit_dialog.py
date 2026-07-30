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
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..library_audit.checker import (
    audit_library,
)
from ..library_audit.models import (
    LibraryAuditSummary,
)
from ..models.song import Song


ERROR_COLOR = QColor(
    255,
    205,
    210,
)
WARNING_COLOR = QColor(
    255,
    239,
    184,
)
GOOD_COLOR = QColor(
    214,
    245,
    222,
)
STATUS_FOREGROUND = QColor(35, 42, 38)


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
        language: str = "automatic",
    ):
        super().__init__(parent)

        self.language = language
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
                tr("library_audit", language)
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
            tr("audit_not_run", language)
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(
            self.status_label
        )

        self.filter_combo = QComboBox()
        self.filter_combo.addItem(
            tr("filter_all", language),
            "all",
        )
        self.filter_combo.addItem(
            tr("filter_errors", language),
            "error",
        )
        self.filter_combo.addItem(
            tr("filter_warnings", language),
            "warning",
        )
        self.filter_combo.addItem(
            tr("filter_info", language),
            "info",
        )
        self.filter_combo.currentIndexChanged.connect(
            self.refresh_table
        )

        self.selected_button = QPushButton(
            tr("check_selected", language, count=len(selected_songs))
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

        self.all_button = QPushButton(
            tr("check_all", language, count=len(all_songs))
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

        self.stats_button = QPushButton(tr("quality_stats", language))
        self.stats_button.clicked.connect(self._open_quality_stats)

        # Kompakte Kopfzeile: Aktions-Buttons und Filter in einer Reihe, damit
        # oben kein hoher Leerraum entsteht und die Breite genutzt wird.
        controls = QHBoxLayout()
        controls.addWidget(self.selected_button, 2)
        controls.addWidget(self.all_button, 2)
        controls.addWidget(self.stats_button, 1)
        controls.addWidget(self.filter_combo, 1)
        layout.addLayout(controls)

        splitter = QSplitter()

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                tr("col_level", language),
                tr("col_category", language),
                tr("col_album", language),
                tr("col_title", language),
                tr("col_message", language),
                tr("col_file", language),
                tr("col_details", language),
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
            QLabel(tr("col_details", language))
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

        # Stretch=1: der Splitter (Tabelle + Details) nimmt den restlichen Platz
        # ein und zieht die Kopfzeile nach oben (kein Leerraum mehr).
        layout.addWidget(
            splitter,
            1,
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

    def _open_quality_stats(self) -> None:
        from .quality_stats_dialog import QualityStatsDialog

        paths = [s.path for s in (self.all_songs or []) if s.path]
        QualityStatsDialog(paths, self, language=self.language).exec()

    def set_songs(
        self,
        selected_songs: list[Song],
        all_songs: list[Song],
    ) -> None:
        self.selected_songs = list(selected_songs)
        self.all_songs = list(all_songs)
        self.selected_button.setText(
            tr("check_selected", self.language, count=len(self.selected_songs))
        )
        self.selected_button.setEnabled(
            bool(self.selected_songs)
        )
        self.all_button.setText(
            tr("check_all", self.language, count=len(self.all_songs))
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
            tr("audit_running", self.language)
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
            tr(
                "audit_summary",
                self.language,
                files=summary.checked_files,
                albums=summary.checked_albums,
                errors=summary.error_count,
                warnings=summary.warning_count,
                info=summary.info_count,
                health=summary.health_score,
            )
        )
        self.refresh_table()

    def audit_failed(
        self,
        message: str,
    ):
        self.status_label.setText(
            tr("audit_failed_status", self.language, message=message)
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
                    issue.severity,
                    self.language,
                ),
                issue.category,
                issue.album_display,
                issue.title,
                issue.message,
                issue.path,
                (
                    tr("master_present", self.language)
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
                color = severity_color(
                    issue.severity
                )
                if color is not None:
                    item.setBackground(color)
                    item.setForeground(
                        STATUS_FOREGROUND
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
            details or tr("no_details", self.language)
        )


def severity_label(
    severity: str,
    language: str = "automatic",
) -> str:
    return {
        "error": tr("severity_error", language),
        "warning": tr("severity_warning", language),
        "info": tr("severity_info", language),
    }.get(
        severity,
        severity,
    )


def severity_color(
    severity: str,
) -> QColor | None:
    return {
        "error": ERROR_COLOR,
        "warning": WARNING_COLOR,
        "info": None,
    }.get(
        severity,
        GOOD_COLOR,
    )
