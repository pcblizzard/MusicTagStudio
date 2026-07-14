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
    ):
        super().__init__()
        self.manager = manager
        self.plans = plans
        self.reuse_existing_master = (
            reuse_existing_master
        )
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
                            "Kein Cover gefunden."
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
            "Verarbeitung abgeschlossen",
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
    ):
        super().__init__(parent)

        self.manager = manager
        self.plans = plans
        self.thread_pool = (
            QThreadPool.globalInstance()
        )

        self.setWindowTitle(
            "Cover für mehrere Alben"
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
            f"{len(plans)} Alben · "
            f"{total_tracks} Audiodateien · "
            f"{existing_count} vorhandene Master-Cover. "
            "Vorhandene Master-Cover werden wiederverwendet. "
            "Für fehlende Cover wird automatisch die beste "
            "unterstützte Quelle gewählt."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.table = QTableWidget(
            len(plans),
            5,
        )
        self.table.setHorizontalHeaderLabels(
            [
                "Album",
                "Titel",
                "Master-Cover",
                "Auflösung",
                "Status",
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
                    "Vorhanden"
                    if existing is not None
                    else "Fehlt"
                ),
                (
                    existing.dimensions
                    if existing is not None
                    else ""
                ),
                "Bereit",
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
            "Noch nicht gestartet."
        )
        layout.addWidget(
            self.status_label
        )

        self.start_button = QPushButton(
            "Cover-Verarbeitung starten"
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
            (
                f"{len(results)} Alben verarbeitet, "
                f"{len(failures)} Fehler."
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
                        f"Fehler: {failure}"
                        if failure
                        else "Abgeschlossen"
                    )
                ),
            )

        message = (
            f"{len(results)} Alben wurden verarbeitet."
        )

        if failures:
            message += (
                "\n\nFehler:\n"
                + "\n".join(
                    f"{name}: {error}"
                    for name, error in failures
                )
            )

        QMessageBox.information(
            self,
            "Cover-Verarbeitung abgeschlossen",
            message,
        )

    def processing_failed(
        self,
        message: str,
    ):
        self.start_button.setEnabled(True)
        QMessageBox.critical(
            self,
            "Cover-Verarbeitung fehlgeschlagen",
            message,
        )
