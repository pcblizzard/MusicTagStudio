from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from ...database import connect_database
from ...diagnostics import project_root
from .models import AvailabilityStatus, StreamingAvailability


class StreamingAvailabilityCache:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(
            path
            or project_root()
            / "cache"
            / "media_library"
            / "streaming_availability.sqlite3"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with connect_database(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS streaming_availability (
                    provider TEXT NOT NULL,
                    release_key TEXT NOT NULL,
                    country TEXT NOT NULL,
                    status TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    external_url TEXT NOT NULL,
                    album TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    year TEXT NOT NULL,
                    track_count INTEGER NOT NULL,
                    confidence INTEGER NOT NULL,
                    checked_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY(provider, release_key, country)
                )
                """
            )

    def get(
        self, provider: str, release_key: str, country: str
    ) -> StreamingAvailability | None:
        with connect_database(self.path) as connection:
            row = connection.execute(
                """SELECT status, external_id, external_url, album, artist,
                          year, track_count, confidence, checked_at, expires_at
                   FROM streaming_availability
                   WHERE provider = ? AND release_key = ? AND country = ?""",
                (provider, release_key, country.upper()),
            ).fetchone()
            if row is None:
                return None
            try:
                result = StreamingAvailability(
                    provider=provider, release_key=release_key,
                    country=country.upper(), status=AvailabilityStatus(row[0]),
                    external_id=row[1], external_url=row[2], album=row[3],
                    artist=row[4], year=row[5], track_count=int(row[6]),
                    confidence=int(row[7]), checked_at=row[8], expires_at=row[9],
                )
            except (TypeError, ValueError):
                connection.execute(
                    "DELETE FROM streaming_availability WHERE provider=? AND release_key=? AND country=?",
                    (provider, release_key, country.upper()),
                )
                return None
            if result.is_expired():
                connection.execute(
                    "DELETE FROM streaming_availability WHERE provider=? AND release_key=? AND country=?",
                    (provider, release_key, country.upper()),
                )
                return None
            return result

    def put(self, result: StreamingAvailability) -> None:
        values = asdict(result)
        values["status"] = result.status.value
        with connect_database(self.path) as connection:
            connection.execute(
                """INSERT INTO streaming_availability
                   (provider, release_key, country, status, external_id,
                    external_url, album, artist, year, track_count, confidence,
                    checked_at, expires_at)
                   VALUES (:provider, :release_key, :country, :status,
                    :external_id, :external_url, :album, :artist, :year,
                    :track_count, :confidence, :checked_at, :expires_at)
                   ON CONFLICT(provider, release_key, country) DO UPDATE SET
                    status=excluded.status, external_id=excluded.external_id,
                    external_url=excluded.external_url, album=excluded.album,
                    artist=excluded.artist, year=excluded.year,
                    track_count=excluded.track_count,
                    confidence=excluded.confidence,
                    checked_at=excluded.checked_at, expires_at=excluded.expires_at""",
                values,
            )
