from __future__ import annotations

from pathlib import Path
import sqlite3


SQLITE_BUSY_TIMEOUT_MS = 10_000


def connect_database(path: str | Path) -> sqlite3.Connection:
    """Open a local cache database with a bounded wait for concurrent writers."""
    connection = sqlite3.connect(
        path,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
    )
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    return connection
