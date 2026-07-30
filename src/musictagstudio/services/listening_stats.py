"""Hör-Statistik: gespielte Zeit je Titel/Künstler/Album/Genre.

Lokal als JSON gespeichert. :meth:`record` addiert die tatsächlich gespielte
Zeit (der Aufrufer misst sie über die Wiedergabe-Engine) auf alle Dimensionen
des Titels. Abfragen liefern die Bestenlisten (z. B. „meistgehörte Künstler").
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models.song import Song

DIMENSIONS = ("song", "artist", "album", "genre")
# Wiedergaben unter dieser Dauer (Sekunden) werden ignoriert (z. B. Durchskippen).
_MIN_SECONDS = 5.0


def _bucket_key(dimension: str, song: Song) -> str:
    if dimension == "song":
        return str(song.path or "")
    if dimension == "artist":
        return str(song.album_artist or song.artist or "").strip()
    if dimension == "album":
        return str(song.album or "").strip()
    return str(song.genre or "").strip()


class ListeningStats:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict[str, dict[str, float]] = {dim: {} for dim in DIMENSIONS}
        self._load()

    def record(self, song: Song, seconds: float) -> None:
        """Addiert gespielte Sekunden auf alle Dimensionen des Titels."""
        if song is None or seconds < _MIN_SECONDS:
            return
        changed = False
        for dimension in DIMENSIONS:
            key = _bucket_key(dimension, song)
            if key:
                self._data[dimension][key] = (
                    self._data[dimension].get(key, 0.0) + float(seconds)
                )
                changed = True
        if changed:
            self._save()

    def total(self, dimension: str, key: str) -> float:
        return self._data.get(dimension, {}).get(key, 0.0)

    def top(self, dimension: str, limit: int = 10) -> list[tuple[str, float]]:
        items = self._data.get(dimension, {}).items()
        return sorted(items, key=lambda kv: kv[1], reverse=True)[:limit]

    def grand_total(self, dimension: str = "song") -> float:
        return sum(self._data.get(dimension, {}).values())

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        for dimension in DIMENSIONS:
            values = data.get(dimension, {})
            if isinstance(values, dict):
                self._data[dimension] = {
                    str(k): float(v)
                    for k, v in values.items()
                    if _is_number(v)
                }

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def format_duration(seconds: float) -> str:
    """Menschlich lesbar: '3 Tage 4 Std', '2 Std 15 Min', '45 Min', '30 Sek'."""
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{days} Tage {hours} Std"
    if hours:
        return f"{hours} Std {minutes} Min"
    if minutes:
        return f"{minutes} Min"
    return f"{secs} Sek"


def default_stats_path() -> Path:
    from ..diagnostics import user_data_dir

    return Path(user_data_dir()) / "listening_stats.json"
