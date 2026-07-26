from __future__ import annotations

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    Signal,
    Slot,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..cover_management.batch import (
    AlbumCoverPlan,
)
from ..cover_management.manager import (
    CoverManager,
)
from ..i18n import tr


class WorkerSignals(QObject):
    progress = Signal(
        int,
        int,
        str,
    )
    finished = Signal(object)
    failed = Signal(str)


class BatchCoverWorker(QRunnable):
    def __init__(
        self,
        manager: CoverManager,
        plans: list[AlbumCoverPlan],
        reuse_existing_master: bool,
        language: str = "automatic",
    ):
        super().__init__()
        self.manager = manager
        self.plans = plans
        self.reuse_existing_master = (
            reuse_existing_master
        )
        self.language = language
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        results = []
        failures = []

        for index, plan in enumerate(
            self.plans,
            start=1,
        ):
            self.signals.progress.emit(
                index - 1,
                len(self.plans),
                plan.display_name,
            )

            try:
                candidate = None

                if (
                    self.reuse_existing_master
                    and plan.existing_master is not None
                ):
                    candidate = plan.existing_master
                else:
                    candidates = (
                        self.manager.search_candidates(
                            plan.songs[0]
                        )
                    )

                    if not candidates:
                        raise RuntimeError(
                            tr("no_cover_found", self.language)
                        )

                    candidate = max(
                        candidates,
                        key=lambda item:
                        item.score,
                    )

                result = self.manager.apply(
                    candidate,
                    list(plan.songs),
                )
                results.append(
                    (
                        plan.display_name,
                        result,
                    )
                )
            except Exception as error:
                failures.append(
                    (
                        plan.display_name,
                        str(error),
                    )
                )

        self.signals.progress.emit(
            len(self.plans),
            len(self.plans),
            tr("processing_done", self.language),
        )
        self.signals.finished.emit(
            {
                "results": results,
                "failures": failures,
            }
        )


class BatchCoverDialog(QDialog):
    def __init__(
        self,
        manager: CoverManager,
        plans: list[AlbumCoverPlan],
        parent=None,
        language: str = "automatic",
    ):
        super().__init__(parent)

        self.manager = manager
        self.plans = plans
        self.language = language
        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self.setWindowTitle(
            tr("batch_cover_title", language)
        )
        self.resize(
            980,
            650,
        )

        layout = QVBoxLayout(self)

        existing_count = sum(
            1
            for plan in plans
            if plan.existing_master is not None
        )
        total_tracks = sum(
            plan.track_count
            for plan in plans
        )

        info = QLabel(
            tr(
                "batch_cover_info",
                language,
                albums=len(plans),
                tracks=total_tracks,
                existing=existing_count,
            )
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget(
            len(plans),
            5,
        )
        self.table.setHorizontalHeaderLabels(
            [
                tr("col_album", language),
                tr("col_title", language),
                tr("master_cover", language),
                tr("resolution", language),
                tr("col_status", language),
            ]
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        for row, plan in enumerate(plans):
            existing = plan.existing_master

            values = [
                plan.display_name,
                str(plan.track_count),
                (
                    tr("master_present", language)
                    if existing is not None
                    else tr("master_missing", language)
                ),
                (
                    existing.dimensions
                    if existing is not None
                    else ""
                ),
                tr("status_ready", language),
            ]

            for column, value in enumerate(
                values
            ):
                self.table.setItem(
                    row,
                    column,
                    QTableWidgetItem(value),
                )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )

        for column in range(1, 5):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        layout.addWidget(self.table)

        self.progress = QProgressBar()
        self.progress.setMaximum(
            max(1, len(plans))
        )
        layout.addWidget(self.progress)

        self.status_label = QLabel(
            tr("status_not_started", language)
        )
        layout.addWidget(
            self.status_label
        )

        self.start_button = QPushButton(
            tr("start_cover_processing", language)
        )
        self.start_button.clicked.connect(
            self.start_processing
        )
        layout.addWidget(
            self.start_button
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close
        )
        buttons.rejected.connect(
            self.reject
        )
        layout.addWidget(buttons)

    def start_processing(self):
        self.start_button.setEnabled(False)

        worker = BatchCoverWorker(
            self.manager,
            self.plans,
            reuse_existing_master=True,
            language=self.language,
        )
        worker.signals.progress.connect(
            self.update_progress
        )
        worker.signals.finished.connect(
            self.processing_finished
        )
        worker.signals.failed.connect(
            self.processing_failed
        )
        self.thread_pool.start(worker)

    def update_progress(
        self,
        value: int,
        maximum: int,
        text: str,
    ):
        self.progress.setMaximum(
            max(1, maximum)
        )
        self.progress.setValue(value)
        self.status_label.setText(text)

    def processing_finished(
        self,
        payload,
    ):
        self.start_button.setEnabled(True)

        results = payload["results"]
        failures = payload["failures"]

        self.status_label.setText(
            tr(
                "batch_cover_progress",
                self.language,
                done=len(results),
                failed=len(failures),
            )
        )

        for row, plan in enumerate(
            self.plans
        ):
            failure = next(
                (
                    message
                    for name, message
                    in failures
                    if name == plan.display_name
                ),
                None,
            )
            self.table.setItem(
                row,
                4,
                QTableWidgetItem(
                    (
                        tr("error_status", self.language, message=failure)
                        if failure
                        else tr("row_done", self.language)
                    )
                ),
            )

        message = tr("batch_cover_done_msg", self.language, count=len(results))

        if failures:
            message += tr(
                "errors_block",
                self.language,
                errors="\n".join(
                    f"{name}: {error}" for name, error in failures
                ),
            )

        QMessageBox.information(
            self,
            tr("cover_batch_done_title", self.language),
            message,
        )

    def processing_failed(
        self,
        message: str,
    ):
        self.start_button.setEnabled(True)
        QMessageBox.critical(
            self,
            tr("cover_failed_title", self.language),
            message,
        )
