from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from ..diagnostics import project_root
from .models import LyricsDocument, LyricsLine


class LyricsCache:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(
            path or project_root() / "cache" / "lyrics" / "lyrics.sqlite3"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS lyrics_cache (
                    cache_key TEXT PRIMARY KEY,
                    document_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                )
                """
            )

    def get(self, cache_key: str) -> LyricsDocument | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT document_json FROM lyrics_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row[0])
            payload["synced_lines"] = tuple(
                LyricsLine(**line) for line in payload.get("synced_lines", [])
            )
            return LyricsDocument(**payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def put(self, cache_key: str, document: LyricsDocument) -> None:
        payload = asdict(document)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO lyrics_cache(cache_key, document_json, fetched_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    document_json = excluded.document_json,
                    fetched_at = excluded.fetched_at
                """,
                (
                    cache_key,
                    json.dumps(payload, ensure_ascii=False),
                    document.fetched_at or LyricsDocument.now_iso(),
                ),
            )


def lyrics_cache_key(
    title: str,
    artist: str,
    album: str,
    duration: int | float,
) -> str:
    fields = (title, artist, album)
    normalized = [" ".join(str(value or "").casefold().split()) for value in fields]
    normalized.append(str(round(float(duration))))
    return "\x1f".join(normalized)
