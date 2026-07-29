from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import re
import unicodedata


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    NOT_CHECKED = "not_checked"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True)
class StreamingAvailability:
    provider: str
    release_key: str
    status: AvailabilityStatus
    external_id: str = ""
    external_url: str = ""
    album: str = ""
    artist: str = ""
    year: str = ""
    track_count: int = 0
    confidence: int = 0
    country: str = ""
    checked_at: str = ""
    expires_at: str = ""
    # Tagesgenaues Veröffentlichungsdatum (ISO) für die Vorab-Erkennung.
    release_date: str = ""
    # Optionales Qualitätskennzeichen des Anbieters (z. B. TIDAL "Hi-Res
    # Lossless"). Wird nicht zwischengespeichert -> nur direkt nach der Prüfung.
    quality: str = ""

    @classmethod
    def available(
        cls, *, provider: str, release_key: str, external_id: str,
        external_url: str, album: str, artist: str, year: str,
        track_count: int, confidence: int, country: str,
        release_date: str = "",
        quality: str = "",
        ttl_days: int = 7,
    ) -> "StreamingAvailability":
        checked = datetime.now().astimezone()
        return cls(
            provider=provider, release_key=release_key,
            status=AvailabilityStatus.AVAILABLE,
            external_id=external_id, external_url=external_url,
            album=album, artist=artist, year=year,
            track_count=track_count, confidence=confidence, country=country,
            release_date=release_date, quality=quality,
            checked_at=checked.isoformat(timespec="seconds"),
            expires_at=(checked + timedelta(days=ttl_days)).isoformat(timespec="seconds"),
        )

    @classmethod
    def checked(
        cls,
        *,
        provider: str,
        release_key: str,
        status: AvailabilityStatus,
        country: str,
        ttl_minutes: int = 30,
    ) -> "StreamingAvailability":
        checked = datetime.now().astimezone()
        return cls(
            provider=provider,
            release_key=release_key,
            status=status,
            country=country.upper(),
            checked_at=checked.isoformat(timespec="seconds"),
            expires_at=(checked + timedelta(minutes=ttl_minutes)).isoformat(
                timespec="seconds"
            ),
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        if not self.expires_at:
            return True
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            if expiry.tzinfo is None:
                expiry = expiry.astimezone()
        except ValueError:
            return True
        return (now or datetime.now().astimezone()) >= expiry


def streaming_release_key(artist: str, album: str, year: str = "") -> str:
    def normalize(value: str) -> str:
        value = unicodedata.normalize("NFKD", str(value or "").casefold())
        value = "".join(c for c in value if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", "", value)

    return "|".join((normalize(artist), normalize(album), str(year or "")[:4]))
