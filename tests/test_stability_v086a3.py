from concurrent.futures import ThreadPoolExecutor
import json
import threading
from urllib.error import URLError
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from musictagstudio import __version__
from musictagstudio.database import SQLITE_BUSY_TIMEOUT_MS, connect_database
from musictagstudio.direct_album_lookup import _lookup_apple_song
from musictagstudio.local_track import title_from_filename
from musictagstudio.media_library import discogs
from musictagstudio.providers import apple_editorial, apple_music, theaudiodb
from musictagstudio.providers import apple_http


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps({"ok": True}).encode()


def test_discogs_network_wait_does_not_hold_global_pacing_lock(monkeypatch):
    barrier = threading.Barrier(2)

    def urlopen(_request, timeout):
        assert timeout == 20
        barrier.wait(timeout=2)
        return _Response()

    monkeypatch.setattr(discogs.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(discogs, "REQUEST_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(discogs, "_last_request_at", 0.0)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(discogs._get_json, "/test", "token", {"n": str(index)})
            for index in range(2)
        ]
        assert [future.result(timeout=3) for future in futures] == [
            {"ok": True},
            {"ok": True},
        ]


@pytest.mark.parametrize("provider", [theaudiodb, apple_editorial])
def test_editorial_network_errors_are_typed(provider, monkeypatch, tmp_path):
    monkeypatch.setattr(provider, "project_root", lambda: tmp_path)
    monkeypatch.setattr(
        provider,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")),
    )

    with pytest.raises(theaudiodb.EditorialProviderError):
        if provider is theaudiodb:
            provider._get_json("search.php", {"s": "Clueso"})
        else:
            provider._get_page(
                "https://music.apple.com/de/album/example/123",
                "de",
            )


def test_cache_database_waits_for_concurrent_writer(tmp_path):
    with connect_database(tmp_path / "cache.sqlite3") as connection:
        value = connection.execute("PRAGMA busy_timeout").fetchone()[0]
    assert value == SQLITE_BUSY_TIMEOUT_MS


def test_filename_title_is_consistent_for_windows_and_posix_paths():
    expected = "Liebe auf den letzten Blick"
    assert title_from_filename(r"C:\Music\02. Clueso - Liebe auf den letzten Blick.flac") == expected
    assert title_from_filename("/Music/02. Clueso - Liebe auf den letzten Blick.flac") == expected


def test_apple_user_agent_tracks_package_version():
    assert apple_music.USER_AGENT == f"MusicTagStudio/{__version__}"


def test_direct_apple_song_lookup_builds_request_and_year(monkeypatch):
    calls = []

    def request_json(endpoint, params):
        calls.append((endpoint, params))
        return {
            "results": [
                {
                    "wrapperType": "track",
                    "kind": "song",
                    "trackName": "Example",
                    "artistName": "Artist",
                    "collectionName": "Album",
                    "releaseDate": "2026-07-24T00:00:00Z",
                    "trackId": 123,
                }
            ]
        }

    monkeypatch.setattr(
        "musictagstudio.direct_album_lookup._request_json",
        request_json,
    )
    result = _lookup_apple_song("123", country="DE")

    assert result.tracks[0].year == "2026"
    assert calls == [
        (
            "https://itunes.apple.com/lookup",
            {"id": "123", "country": "DE", "entity": "song"},
        )
    ]


def test_apple_http_retries_429_with_bounded_retry_after(monkeypatch):
    calls = 0
    sleeps = []

    def urlopen(_request, timeout):
        nonlocal calls
        calls += 1
        assert timeout == 15
        if calls == 1:
            raise HTTPError(
                "https://itunes.apple.com/search",
                429,
                "rate limited",
                {"Retry-After": "99"},
                None,
            )
        return _Response()

    monkeypatch.setattr(apple_http, "urlopen", urlopen)
    monkeypatch.setattr(apple_http, "REQUEST_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(apple_http, "_last_request_at", 0.0)
    monkeypatch.setattr(apple_http.time, "sleep", sleeps.append)

    result = apple_http.request_json(
        Request("https://itunes.apple.com/search"),
        timeout=15,
    )

    assert result == {"ok": True}
    assert calls == 2
    assert sleeps == [apple_http.MAX_RETRY_AFTER_SECONDS]


def test_apple_http_does_not_hold_pacing_lock_during_network(monkeypatch):
    barrier = threading.Barrier(2)

    def urlopen(_request, timeout):
        assert timeout == 15
        barrier.wait(timeout=2)
        return _Response()

    monkeypatch.setattr(apple_http, "urlopen", urlopen)
    monkeypatch.setattr(apple_http, "REQUEST_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(apple_http, "_last_request_at", 0.0)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                apple_http.request_json,
                Request(f"https://itunes.apple.com/search?n={index}"),
                timeout=15,
            )
            for index in range(2)
        ]
        assert [future.result(timeout=3) for future in futures] == [
            {"ok": True},
            {"ok": True},
        ]
