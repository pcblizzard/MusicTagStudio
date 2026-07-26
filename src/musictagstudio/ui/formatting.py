"""Kleine, UI-nahe Formatierungshelfer."""

from __future__ import annotations

import re

from PySide6.QtCore import QDate, QLocale


def localized_date(iso: str) -> str:
    """Formatiert ein ISO-Datum (YYYY-MM-DD…) gemäß Systemsprache.

    Beispiel (deutsches System): "2026-10-01T07:00:00Z" -> "01.10.2026".
    Bei ungültigem/leerem Wert werden die ersten 10 Zeichen zurückgegeben.
    """
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or "").strip())
    if not match:
        return str(iso or "")[:10]
    qdate = QDate(
        int(match.group(1)), int(match.group(2)), int(match.group(3))
    )
    if not qdate.isValid():
        return str(iso)[:10]
    return QLocale.system().toString(qdate, QLocale.FormatType.ShortFormat)
