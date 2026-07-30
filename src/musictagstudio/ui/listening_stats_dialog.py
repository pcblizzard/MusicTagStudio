from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..i18n import tr
from ..services.listening_stats import ListeningStats, format_duration


class ListeningStatsDialog(QDialog):
    """Zeigt die meistgehörten Titel/Künstler/Alben/Genres (nach Zeit)."""

    def __init__(
        self, stats: ListeningStats, parent=None, *, language: str = "automatic"
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(tr("stats_title", language))
        self.resize(560, 520)

        layout = QVBoxLayout(self)
        total = format_duration(stats.grand_total("song"))
        summary = QLabel(tr("stats_total", language, total=total))
        summary.setStyleSheet("font-weight: 600;")
        layout.addWidget(summary)

        tabs = QTabWidget()
        for dimension, label_key in (
            ("song", "stats_tab_songs"),
            ("artist", "stats_tab_artists"),
            ("album", "stats_tab_albums"),
            ("genre", "stats_tab_genres"),
        ):
            tabs.addTab(
                self._make_tab(stats, dimension), tr(label_key, language)
            )
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _make_tab(self, stats: ListeningStats, dimension: str) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setColumnCount(2)
        tree.setHeaderLabels(
            [tr("stats_col_name", self.language), tr("stats_col_time", self.language)]
        )
        rows = stats.top(dimension, 25)
        if not rows:
            tree.addTopLevelItem(
                QTreeWidgetItem([tr("stats_empty", self.language), ""])
            )
        for key, seconds in rows:
            name = Path(key).name if dimension == "song" else key
            tree.addTopLevelItem(
                QTreeWidgetItem([name or "—", format_duration(seconds)])
            )
        tree.resizeColumnToContents(0)
        return tree
