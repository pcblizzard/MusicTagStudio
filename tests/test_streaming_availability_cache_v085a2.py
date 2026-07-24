from dataclasses import replace
from datetime import datetime, timedelta

from musictagstudio.media_library.streaming import (
    AvailabilityStatus, StreamingAvailability, StreamingAvailabilityCache,
    streaming_release_key,
)


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


def test_release_key_normalizes_accents_and_punctuation() -> None:
    assert streaming_release_key("Clüeso", "Deja Vu 1/2", "2026-02-27") == (
        "clueso|dejavu12|2026"
    )
