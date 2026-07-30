"""Favoriten: Titel/Alben/Künstler/Genres als Lieblinge markieren.

Lokal als JSON gespeichert. Titel werden über den Dateipfad identifiziert,
Künstler/Album/Genre über den (normalisierten) Namen.
"""

from __future__ import annotations

import json
from pathlib import Path

KINDS = ("song", "artist", "album", "genre")


def _key(kind: str, value: str) -> str:
    value = str(value or "").strip()
    return value if kind == "song" else value.casefold()


class Favorites:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict[str, set[str]] = {kind: set() for kind in KINDS}
        self._load()

    def is_favorite(self, kind: str, value: str) -> bool:
        return _key(kind, value) in self._data.get(kind, set())

    def add(self, kind: str, value: str) -> None:
        key = _key(kind, value)
        if kind in self._data and key:
            self._data[kind].add(key)
            self._save()

    def remove(self, kind: str, value: str) -> None:
        key = _key(kind, value)
        if kind in self._data and key in self._data[kind]:
            self._data[kind].discard(key)
            self._save()

    def toggle(self, kind: str, value: str) -> bool:
        """Kehrt den Favoriten-Status um und gibt den neuen Status zurück."""
        if self.is_favorite(kind, value):
            self.remove(kind, value)
            return False
        self.add(kind, value)
        return True

    def all(self, kind: str) -> set[str]:
        return set(self._data.get(kind, set()))

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        for kind in KINDS:
            values = data.get(kind, [])
            if isinstance(values, list):
                self._data[kind] = {str(v) for v in values}

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(
                    {kind: sorted(values) for kind, values in self._data.items()},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass


def default_favorites_path() -> Path:
    from ..diagnostics import user_data_dir

    return Path(user_data_dir()) / "favorites.json"
