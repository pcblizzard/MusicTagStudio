from __future__ import annotations

import json

import pytest

from musictagstudio.providers import genius


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_genius_search_uses_bearer_token_and_parses_song(monkeypatch) -> None:
    monkeypatch.setattr(genius, "REQUEST_INTERVAL_SECONDS", 0)
    captured = {}

    def fake_urlopen(request, timeout):
        if "/songs/42" in request.full_url:
            return _Response(
                {
                    "response": {
                        "song": {
                            "album": {
                                "name": "Moai",
                            }
                        }
                    }
                }
            )
        captured["authorization"] = request.get_header("Authorization")
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _Response(
            {
                "response": {
                    "hits": [
                        {
                            "type": "song",
                            "result": {
                                "id": 42,
                                "title_with_featured": "California Love",
                                "artist_names": "2Pac feat. Dr. Dre",
                                "url": "https://genius.com/example",
                            },
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(genius, "urlopen", fake_urlopen)
    results = genius.search_songs_by_text(
        "California knows how to party",
        access_token="secret-token",
    )

    assert captured["authorization"] == "Bearer secret-token"
    assert "q=California+knows+how+to+party" in captured["url"]
    assert captured["timeout"] == 15
    assert results[0].title == "California Love"
    assert results[0].artist == "2Pac feat. Dr. Dre"
    assert results[0].album == "Moai"


def test_genius_search_without_token_does_not_contact_network(
    monkeypatch,
) -> None:
    def unexpected_call(*_args, **_kwargs):
        pytest.fail("Network must not be contacted without a token")

    monkeypatch.setattr(genius, "urlopen", unexpected_call)
    assert genius.search_songs_by_text("remembered line", access_token="") == []


def test_validate_access_token_uses_search_not_account(monkeypatch) -> None:
    # Regression: /account verlangt die OAuth-Berechtigung "me", die ein
    # Client Access Token nicht hat -> ein gültiges Token würde abgelehnt.
    # Die Prüfung muss gegen den tatsächlich genutzten /search-Endpunkt gehen.
    called = {}

    def fake_urlopen(request, timeout):
        called["url"] = request.full_url
        called["auth"] = request.headers.get("Authorization")
        return _Response({"response": {"hits": []}})

    monkeypatch.setattr(genius, "urlopen", fake_urlopen)
    genius.validate_access_token("token-123")
    assert "/search" in called["url"]
    assert "/account" not in called["url"]
    assert called["auth"] == "Bearer token-123"


def test_genius_requests_share_one_global_pacing_lock(monkeypatch) -> None:
    starts = iter([0.25, 1.0])
    sleeps = []
    monkeypatch.setattr(genius, "REQUEST_INTERVAL_SECONDS", 1.0)
    monkeypatch.setattr(genius.time, "monotonic", lambda: next(starts))
    monkeypatch.setattr(genius.time, "sleep", sleeps.append)
    monkeypatch.setattr(genius, "_last_request_started", 0.0)

    genius._pace_request()

    assert sleeps == [0.75]


def test_genius_only_enriches_the_first_detail_candidates(monkeypatch) -> None:
    monkeypatch.setattr(genius, "REQUEST_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(genius, "DETAIL_ENRICHMENT_LIMIT", 2)
    detail_requests = []

    def fake_urlopen(request, timeout):
        if "/songs/" in request.full_url:
            detail_requests.append(request.full_url)
            return _Response({"response": {"song": {"album": {"name": "Album"}}}})
        return _Response(
            {
                "response": {
                    "hits": [
                        {
                            "type": "song",
                            "result": {
                                "id": index,
                                "title": f"Song {index}",
                                "artist_names": "Artist",
                                "url": f"https://genius.com/{index}",
                            },
                        }
                        for index in range(1, 5)
                    ]
                }
            }
        )

    monkeypatch.setattr(genius, "urlopen", fake_urlopen)

    results = genius.search_songs_by_text("remembered line", access_token="token")

    assert len(results) == 4
    assert len(detail_requests) == 2
