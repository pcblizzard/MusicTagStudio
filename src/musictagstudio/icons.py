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
    # Wie "shuffle", aber mit Punkt-Badge unten – kennzeichnet "immer neu
    # auslosen" (analog zum Punkt bei "repeat_one").
    "shuffle_fresh": (
        '<g fill="none" stroke="{color}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M16 4h4v4"/><path d="M4 20 20 4"/>'
        '<path d="M16 20h4v-4"/><path d="m4 4 5 5"/><path d="m15 15 5 5"/></g>'
        '<circle cx="12" cy="21" r="1.8" fill="{color}" stroke="none"/>'
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
