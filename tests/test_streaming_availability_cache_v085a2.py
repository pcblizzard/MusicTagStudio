from dataclasses import replace
from datetime import datetime, timedelta

from musictagstudio.media_library.streaming import (
    AvailabilityStatus, StreamingAvailability, StreamingAvailabilityCache,
    streaming_release_key,
)


def test_negative_streaming_result_uses_short_cache_lifetime():
    result = StreamingAvailability.checked(
        provider="tidal",
        release_key="clueso|dejavu12|2026",
        status=AvailabilityStatus.NOT_FOUND,
        country="DE",
    )

    checked_at = datetime.fromisoformat(result.checked_at)
    expires_at = datetime.fromisoformat(result.expires_at)

    assert expires_at - checked_at == timedelta(minutes=30)


def availability(provider="apple_music", country="DE"):
    return StreamingAvailability.available(
        provider=provider,
        release_key=streaming_release_key("Clueso", "Deja Vu 1/2", "2026"),
        external_id="1859696286",
        external_url="https://music.apple.com/de/album/id1859696286",
        album="Deja Vu 1/2", artist="Clueso", year="2026",
        track_count=14, confidence=99, country=country,
    )


def test_cache_roundtrip(tmp_path) -> None:
    cache = StreamingAvailabilityCache(tmp_path / "streaming.sqlite3")
    expected = availability()
    cache.put(expected)
    loaded = cache.get("apple_music", expected.release_key, "DE")
    assert loaded == expected
    assert loaded.status is AvailabilityStatus.AVAILABLE


def test_cache_separates_providers_and_countries(tmp_path) -> None:
    cache = StreamingAvailabilityCache(tmp_path / "streaming.sqlite3")
    records = (availability(), availability(provider="deezer"), availability(country="US"))
    for record in records:
        cache.put(record)
    for record in records:
        assert cache.get(record.provider, record.release_key, record.country) == record


def test_expired_result_is_removed(tmp_path) -> None:
    cache = StreamingAvailabilityCache(tmp_path / "streaming.sqlite3")
    result = availability()
    cache.put(replace(
        result,
        expires_at=(datetime.now().astimezone() - timedelta(days=1)).isoformat(),
    ))
    assert cache.get("apple_music", result.release_key, "DE") is None


def test_cache_roundtrips_release_date(tmp_path) -> None:
    cache = StreamingAvailabilityCache(tmp_path / "streaming.sqlite3")
    expected = replace(availability(), release_date="2026-10-01T07:00:00Z")
    cache.put(expected)
    loaded = cache.get("apple_music", expected.release_key, "DE")
    assert loaded == expected
    assert loaded.release_date == "2026-10-01T07:00:00Z"


def test_cache_migrates_old_schema_without_release_date(tmp_path) -> None:
    from musictagstudio.database import connect_database

    db = tmp_path / "streaming.sqlite3"
    # Alte Tabelle ohne release_date-Spalte anlegen.
    with connect_database(db) as connection:
        connection.execute(
            """CREATE TABLE streaming_availability (
                provider TEXT NOT NULL, release_key TEXT NOT NULL,
                country TEXT NOT NULL, status TEXT NOT NULL,
                external_id TEXT NOT NULL, external_url TEXT NOT NULL,
                album TEXT NOT NULL, artist TEXT NOT NULL, year TEXT NOT NULL,
                track_count INTEGER NOT NULL, confidence INTEGER NOT NULL,
                checked_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                PRIMARY KEY(provider, release_key, country))"""
        )

    # Konstruktor migriert die Spalte; put/get funktionieren danach.
    cache = StreamingAvailabilityCache(db)
    record = replace(availability(), release_date="2027-01-01")
    cache.put(record)
    assert cache.get("apple_music", record.release_key, "DE") == record


def test_release_key_normalizes_accents_and_punctuation() -> None:
    assert streaming_release_key("Clüeso", "Deja Vu 1/2", "2026-02-27") == (
        "clueso|dejavu12|2026"
    )
