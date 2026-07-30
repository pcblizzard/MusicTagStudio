from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..i18n import tr
from ..services.library_stats import LibraryStats, compute_stats


class _StatsWorker(QObject):
    finished = Signal(object)

    def __init__(self, paths: list[str]) -> None:
        super().__init__()
        self._paths = paths

    @Slot()
    def run(self) -> None:
        self.finished.emit(compute_stats(self._paths))


class QualityStatsDialog(QDialog):
    """Zeigt die Qualitätsverteilung der Sammlung (Format/Bit-Tiefe/Rate)."""

    def __init__(
        self, paths: list[str], parent=None, *, language: str = "automatic"
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(tr("quality_stats", language))
        self.resize(560, 520)

        layout = QVBoxLayout(self)
        self.summary = QLabel(tr("quality_stats_computing", language))
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        layout.addWidget(self.tree)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self._thread = QThread(self)
        self._worker = _StatsWorker(paths)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._show)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _section(self, title: str, rows: list[tuple[str, int]]) -> None:
        parent = QTreeWidgetItem([title, ""])
        parent.setFirstColumnSpanned(True)
        self.tree.addTopLevelItem(parent)
        for label, count in rows:
            parent.addChild(QTreeWidgetItem([label, str(count)]))
        parent.setExpanded(True)

    @Slot(object)
    def _show(self, stats: LibraryStats) -> None:
        self.summary.setText(
            tr(
                "quality_stats_summary",
                self.language,
                readable=stats.readable,
                total=stats.total,
                lossless=stats.lossless,
                percent=f"{stats.lossless_percent:.0f}",
                lossy=stats.lossy,
            )
        )
        self.tree.clear()
        self._section(
            tr("quality_stats_codecs", self.language),
            [(codec, count) for codec, count in stats.by_codec.items()],
        )
        self._section(
            tr("quality_stats_bitdepth", self.language),
            [(f"{bits} Bit", count) for bits, count in stats.by_bit_depth.items()],
        )
        self._section(
            tr("quality_stats_rates", self.language),
            [
                (f"{rate / 1000:.1f} kHz", count)
                for rate, count in stats.by_sample_rate.items()
            ],
        )
        self.tree.resizeColumnToContents(0)
