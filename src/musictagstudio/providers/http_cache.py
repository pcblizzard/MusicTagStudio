from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from ..database import connect_database
from ..diagnostics import project_root


DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS http_cache ("
    "cache_key TEXT PRIMARY KEY, "
    "payload TEXT NOT NULL, "
    "stored_at REAL NOT NULL)"
)


def _cache_path() -> Path:
    return project_root() / "cache" / "provider_http_cache.sqlite3"


def load(
    key: str,
    *,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
) -> dict | None:
    """Liefert eine zwischengespeicherte Antwort, falls noch gültig."""
    path = _cache_path()

    if not path.is_file():
        return None

    try:
        with closing(connect_database(path)) as connection:
            connection.execute(_SCHEMA)
            row = connection.execute(
                "SELECT payload, stored_at FROM http_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return None

    if row is None:
        return None

    payload_text, stored_at = row

    if (time.time() - float(stored_at)) > ttl_seconds:
        return None

    try:
        result = json.loads(payload_text)
    except (json.JSONDecodeError, TypeError):
        return None

    return result if isinstance(result, dict) else None


def store(key: str, payload: dict) -> None:
    """Speichert eine erfolgreiche Antwort dauerhaft mit Zeitstempel."""
    path = _cache_path()

    try:
        serialized = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        return

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(connect_database(path)) as connection:
            connection.execute(_SCHEMA)
            connection.execute(
                "INSERT OR REPLACE INTO http_cache "
                "(cache_key, payload, stored_at) VALUES (?, ?, ?)",
                (key, serialized, time.time()),
            )
            connection.commit()
    except (sqlite3.Error, OSError):
        return


def clear() -> None:
    """Entfernt den gesamten Antwort-Cache."""
    _cache_path().unlink(missing_ok=True)
