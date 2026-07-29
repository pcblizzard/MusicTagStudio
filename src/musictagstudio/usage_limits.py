"""Kostenloses Nutzungskontingent (Freemium) ohne Zeitbezug.

Ohne gültige Lizenz sind einige Premium-Aktionen eine begrenzte Anzahl gratis
nutzbar (z. B. 30 Datei-Umbenennungen), danach erscheint der Premium-Hinweis.
Bewusst nutzungs- statt zeitbasiert: nicht durch Uhr-Manipulation umgehbar.
Der Zähler liegt lokal; ein technisch versierter Nutzer kann ihn zurücksetzen –
als „vor dem Kauf ausprobieren"-Schwelle ist das akzeptabel.
"""

from __future__ import annotations

import json
from pathlib import Path

FREE_RENAME_LIMIT = 30


def default_usage_path() -> Path:
    from .diagnostics import project_root

    return Path(project_root()) / ".musictagstudio" / "usage.json"


def renames_used(path: Path | None = None) -> int:
    target = Path(path) if path is not None else default_usage_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    if not isinstance(data, dict):
        return 0
    try:
        return max(0, int(data.get("renames", 0)))
    except (TypeError, ValueError):
        return 0


def remaining_free_renames(path: Path | None = None) -> int:
    return max(0, FREE_RENAME_LIMIT - renames_used(path))


def record_renames(count: int, path: Path | None = None) -> None:
    target = Path(path) if path is not None else default_usage_path()
    total = renames_used(target) + max(0, int(count))
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"renames": total}), encoding="utf-8")
    except OSError:
        pass
