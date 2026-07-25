from pathlib import Path

import pytest

from musictagstudio.providers import http_cache


@pytest.fixture(autouse=True)
def _redirect_cache(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(http_cache, "project_root", lambda: tmp_path)


def test_store_and_load_roundtrip():
    http_cache.store("https://example/api?x=1", {"a": 1, "b": ["x"]})
    assert http_cache.load("https://example/api?x=1") == {"a": 1, "b": ["x"]}


def test_missing_key_returns_none():
    assert http_cache.load("https://example/missing") is None


def test_expired_entry_returns_none():
    http_cache.store("k", {"v": 1})
    assert http_cache.load("k", ttl_seconds=-1) is None


def test_clear_removes_entries():
    http_cache.store("k", {"v": 1})
    http_cache.clear()
    assert http_cache.load("k") is None


def test_load_without_file_returns_none():
    # No store() called, so no database file exists yet.
    assert http_cache.load("anything") is None
