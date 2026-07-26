"""Einheitliche, monochrome SVG-Icons statt gemischter Emoji.

Die Icons werden als Inline-SVG gehalten (kein Asset-/CDN-Handling) und in der
gewünschten Farbe gerendert, sodass sie sich an helle/dunkle Themes anpassen.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


# {color} wird durch die aktuelle Palette-Farbe ersetzt. Einheitliches
# 24er-Raster; gefüllte Glyphen für Transport, Strich-Icons für den Rest.
_ICONS: dict[str, str] = {
    "play": '<path fill="{color}" d="M8 5v14l11-7z"/>',
    "pause": '<path fill="{color}" d="M7 5h4v14H7zM13 5h4v14h-4z"/>',
    "previous": '<path fill="{color}" d="M6 5h2v14H6zM20 5 9 12l11 7z"/>',
    "next": '<path fill="{color}" d="M16 5h2v14h-2zM4 5l11 7L4 19z"/>',
    "shuffle": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M16 4h4v4"/><path d="M4 20 20 4"/>'
        '<path d="M16 20h4v-4"/><path d="m4 4 5 5"/><path d="m15 15 5 5"/></g>'
    ),
    # Würfel = "immer neu auslosen" (neu auswürfeln); klar unterscheidbar von
    # den Shuffle-Pfeilen des Verlauf-Modus.
    "shuffle_fresh": (
        '<rect x="4" y="4" width="16" height="16" rx="3.5" fill="none" '
        'stroke="{color}" stroke-width="1.8"/>'
        '<g fill="{color}" stroke="none">'
        '<circle cx="8.5" cy="8.5" r="1.5"/><circle cx="15.5" cy="8.5" r="1.5"/>'
        '<circle cx="12" cy="12" r="1.5"/>'
        '<circle cx="8.5" cy="15.5" r="1.5"/><circle cx="15.5" cy="15.5" r="1.5"/>'
        '</g>'
    ),
    "repeat": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M17 2l4 4-4 4"/><path d="M3 12v-2a4 4 0 0 1 4-4h14"/>'
        '<path d="M7 22l-4-4 4-4"/><path d="M21 12v2a4 4 0 0 1-4 4H3"/></g>'
    ),
    "repeat_one": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M17 2l4 4-4 4"/><path d="M3 12v-2a4 4 0 0 1 4-4h14"/>'
        '<path d="M7 22l-4-4 4-4"/><path d="M21 12v2a4 4 0 0 1-4 4H3"/></g>'
        '<circle cx="12" cy="12" r="1.8" fill="{color}" stroke="none"/>'
    ),
    # Navigations-Icons (Seitenleiste).
    "nav_home": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 11 12 4l8 7"/><path d="M6 10v9h12v-9"/>'
        '<path d="M10 19v-5h4v5"/></g>'
    ),
    "nav_tagger": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 4h7l9 9-7 7-9-9z"/></g>'
        '<circle cx="8.5" cy="8.5" r="1.4" fill="{color}" stroke="none"/>'
    ),
    "nav_library": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M9 18V5l11-2v13"/>'
        '<circle cx="6" cy="18" r="2.5"/><circle cx="17" cy="16" r="2.5"/></g>'
    ),
    "nav_analysis": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 12h3l2-6 3 12 3-9 2 3h3"/></g>'
    ),
    "nav_audit": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 3 20 6v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z"/>'
        '<path d="m9 12 2 2 4-4"/></g>'
    ),
    "nav_lyrics": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M5 5h11M5 9h11M5 13h7"/>'
        '<circle cx="17" cy="17" r="3"/><path d="m19.5 19.5 2 2"/></g>'
    ),
    # Rückgängig/Wiederholen (gebogener Pfeil, gespiegelt).
    "undo": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 7v6h6"/>'
        '<path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></g>'
    ),
    "redo": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 7v6h-6"/>'
        '<path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3L21 13"/></g>'
    ),
    # Gefüllter Statuspunkt (Ampel-Ersatz) – Farbe kommt über {color}.
    "dot": '<circle cx="12" cy="12" r="6" fill="{color}"/>',
    "queue": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h10"/></g>'
    ),
    "volume": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 8a5 5 0 0 1 0 8"/></g>'
    ),
    "mute": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 9v6h4l5 4V5L8 9z"/>'
        '<path d="m17 9 4 6M21 9l-4 6"/></g>'
    ),
}


def make_icon(name: str, color: str, size: int = 20) -> QIcon:
    """Rendert ein benanntes Icon in der angegebenen Farbe (Hex/Name)."""
    body = _ICONS[name].format(color=color)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f"{body}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
