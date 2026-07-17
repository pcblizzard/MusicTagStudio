from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..library_sources import IndexedAlbum, MusicSource


class DashboardWidget(QWidget):
    open_workspace = Signal(int)
    refresh_requested = Signal()

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(
            parent
        )
        self._build_ui()

    def _build_ui(
        self,
    ) -> None:
        root = QVBoxLayout(
            self
        )
        root.setContentsMargins(
            28,
            24,
            28,
            24,
        )
        root.setSpacing(
            18
        )

        title = QLabel(
            "Willkommen bei MusicTagStudio"
        )
        title.setStyleSheet(
            "font-size: 25px; font-weight: 700;"
        )
        root.addWidget(
            title
        )

        subtitle = QLabel(
            "Bibliothek verwalten, Metadaten bearbeiten "
            "und die Sammlung prüfen."
        )
        subtitle.setStyleSheet(
            "font-size: 11pt; color: palette(mid);"
        )
        root.addWidget(
            subtitle
        )

        self.cards_layout = QGridLayout()
        self.cards_layout.setHorizontalSpacing(
            14
        )
        self.cards_layout.setVerticalSpacing(
            14
        )
        self.album_value = self._add_card(
            0,
            0,
            "Alben",
            "0",
        )
        self.artist_value = self._add_card(
            0,
            1,
            "Künstler",
            "0",
        )
        self.track_value = self._add_card(
            0,
            2,
            "Indizierte Titel",
            "0",
        )
        self.source_value = self._add_card(
            0,
            3,
            "Musikquellen",
            "0",
        )
        root.addLayout(
            self.cards_layout
        )

        status_box = QFrame()
        status_box.setObjectName(
            "dashboardStatus"
        )
        status_box.setStyleSheet(
            """
            QFrame#dashboardStatus {
                border: 1px solid palette(mid);
                border-radius: 10px;
                background: palette(base);
            }
            """
        )
        status_layout = QVBoxLayout(
            status_box
        )
        status_title = QLabel(
            "Quellenstatus"
        )
        status_title.setStyleSheet(
            "font-size: 13pt; font-weight: 650;"
        )
        status_layout.addWidget(
            status_title
        )
        self.source_status = QLabel(
            "Noch keine Musikquellen eingerichtet."
        )
        self.source_status.setWordWrap(
            True
        )
        status_layout.addWidget(
            self.source_status
        )
        root.addWidget(
            status_box
        )

        quick_title = QLabel(
            "Schnellzugriff"
        )
        quick_title.setStyleSheet(
            "font-size: 13pt; font-weight: 650;"
        )
        root.addWidget(
            quick_title
        )

        quick_row = QHBoxLayout()
        for text, index in (
            ("Tagger öffnen", 0),
            ("Medienbibliothek", 1),
            ("Audio-Analyse", 2),
            ("Bibliothek prüfen", 3),
            ("Einstellungen", 4),
        ):
            button = QPushButton(
                text
            )
            button.setMinimumHeight(
                42
            )
            button.clicked.connect(
                lambda _checked=False, page=index:
                self.open_workspace.emit(
                    page
                )
            )
            quick_row.addWidget(
                button
            )

        root.addLayout(
            quick_row
        )

        refresh = QPushButton(
            "Bibliotheksdaten aktualisieren"
        )
        refresh.clicked.connect(
            self.refresh_requested.emit
        )
        root.addWidget(
            refresh,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        root.addStretch()

    def _add_card(
        self,
        row: int,
        column: int,
        caption: str,
        value: str,
    ) -> QLabel:
        card = QFrame()
        card.setStyleSheet(
            """
            QFrame {
                border: 1px solid palette(mid);
                border-radius: 10px;
                background: palette(base);
            }
            """
        )
        layout = QVBoxLayout(
            card
        )
        number = QLabel(
            value
        )
        number.setStyleSheet(
            "font-size: 25px; font-weight: 700;"
        )
        caption_label = QLabel(
            caption
        )
        caption_label.setStyleSheet(
            "color: palette(mid);"
        )
        layout.addWidget(
            number
        )
        layout.addWidget(
            caption_label
        )
        self.cards_layout.addWidget(
            card,
            row,
            column,
        )
        return number

    def update_library(
        self,
        albums: list[IndexedAlbum],
        sources: tuple[MusicSource, ...],
    ) -> None:
        artists = {
            album.album_artist.casefold()
            for album in albums
            if album.album_artist
        }
        tracks = sum(
            max(
                0,
                album.track_count,
            )
            for album in albums
        )
        online = [
            source
            for source in sources
            if source.enabled
            and source.available
        ]
        offline = [
            source
            for source in sources
            if source.enabled
            and not source.available
        ]

        self.album_value.setText(
            f"{len(albums):,}".replace(
                ",",
                ".",
            )
        )
        self.artist_value.setText(
            f"{len(artists):,}".replace(
                ",",
                ".",
            )
        )
        self.track_value.setText(
            f"{tracks:,}".replace(
                ",",
                ".",
            )
        )
        self.source_value.setText(
            f"{len(online)}/{len([s for s in sources if s.enabled])}"
        )

        lines = []

        if online:
            lines.append(
                "Erreichbar: "
                + ", ".join(
                    source.name
                    for source in online
                )
            )

        if offline:
            lines.append(
                "Nicht erreichbar: "
                + ", ".join(
                    f"{source.name} ({source.path})"
                    for source in offline
                )
            )

        if not lines:
            lines.append(
                "Noch keine aktive Musikquelle eingerichtet."
            )

        self.source_status.setText(
            "\n".join(
                lines
            )
        )
