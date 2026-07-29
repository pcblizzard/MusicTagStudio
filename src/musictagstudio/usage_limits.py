"""Kostenloses Nutzungskontingent (Freemium) + lokale Testphase.

Ohne gültige Lizenz sind einige Premium-Aktionen begrenzt nutzbar:

- **Testphase (zeitbasiert):** in den ersten ``TRIAL_DAYS`` Tagen ab dem ersten
  Start sind die Premium-Funktionen unbegrenzt nutzbar ("ausprobieren").
- **Danach (nutzungsbasiert):** ``FREE_RENAME_LIMIT`` Datei-Umbenennungen bleiben
  dauerhaft gratis, danach erscheint der Premium-Hinweis.

Beides liegt bewusst lokal. Die Testphase ist zeitbasiert und daher durch
Uhr-Manipulation umgehbar – als Kulanz vor dem Kauf ist das akzeptabel; die
harte, nicht per Uhr umgehbare Schwelle bleibt das Umbenennungs-Kontingent.
Ein technisch versierter Nutzer kann die Datei zurücksetzen; als
"vor dem Kauf ausprobieren"-Schwelle ist das in Ordnung.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

FREE_RENAME_LIMIT = 30
TRIAL_DAYS = 3


def default_usage_path() -> Path:
    from .diagnostics import project_root

    return Path(project_root()) / ".musictagstudio" / "usage.json"


def _read(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict) -> None:
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


# --- Nutzungskontingent (nutzungsbasiert) -----------------------------------


def renames_used(path: Path | None = None) -> int:
    data = _read(path if path is not None else default_usage_path())
    try:
        return max(0, int(data.get("renames", 0)))
    except (TypeError, ValueError):
        return 0


def remaining_free_renames(path: Path | None = None) -> int:
    return max(0, FREE_RENAME_LIMIT - renames_used(path))


def record_renames(count: int, path: Path | None = None) -> None:
    target = Path(path) if path is not None else default_usage_path()
    data = _read(target)
    data["renames"] = renames_used(target) + max(0, int(count))
    _write(target, data)


# --- Testphase (zeitbasiert, lokal, bewusst weich) --------------------------


def trial_started_at(path: Path | None = None) -> datetime | None:
    data = _read(path if path is not None else default_usage_path())
    raw = data.get("trial_start")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def ensure_trial_started(now: datetime, path: Path | None = None) -> None:
    """Startet die Testphase beim ersten Aufruf (merkt sich den Zeitpunkt)."""
    target = Path(path) if path is not None else default_usage_path()
    data = _read(target)
    if not data.get("trial_start"):
        data["trial_start"] = now.isoformat(timespec="seconds")
        _write(target, data)


def trial_active(now: datetime, path: Path | None = None) -> bool:
    started = trial_started_at(path)
    if started is None:
        return False
    return now <= started + timedelta(days=TRIAL_DAYS)


def trial_days_remaining(now: datetime, path: Path | None = None) -> int:
    """Verbleibende ganze Tage der Testphase (angebrochener Tag zählt als 1)."""
    started = trial_started_at(path)
    if started is None:
        return 0
    end = started + timedelta(days=TRIAL_DAYS)
    if now >= end:
        return 0
    delta = end - now
    return delta.days + (1 if (delta.seconds or delta.microseconds) else 0)
