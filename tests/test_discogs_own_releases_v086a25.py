from __future__ import annotations

from musictagstudio.media_library import discogs
from musictagstudio.media_library.discogs import _is_own_release_role


def test_own_release_role_keeps_main_and_empty():
    assert _is_own_release_role("Main") is True
    assert _is_own_release_role("main") is True
    assert _is_own_release_role("") is True
    assert _is_own_release_role("   ") is True


def test_own_release_role_drops_appearances_and_credits():
    # Gastauftritte/Features und Produktions-Credits gehoeren nicht in die
    # eigene Diskografie (z. B. ein Feature auf einem fremden Album).
    for role in ("Appearance", "TrackAppearance", "Producer", "Remix", "Mixed By"):
        assert _is_own_release_role(role) is False


def test_fetch_artist_releases_excludes_feature_appearances(monkeypatch):
    pages = {
        1: {
            "releases": [
                {"id": 1, "role": "Main", "title": "Eigenes Album"},
                {"id": 2, "role": "Appearance", "title": "Fremdes Album (feat.)"},
                {"id": 3, "role": "TrackAppearance", "title": "Fremder Sampler"},
            ],
            "pagination": {"pages": 1},
        }
    }

    monkeypatch.setattr(
        discogs,
        "_get_json",
        lambda path, token, params: pages[params["page"]],
    )
    # Detailabruf und Umwandlung auf den Titel reduzieren.
    monkeypatch.setattr(discogs, "_fetch_summary_detail", lambda summary, token: {})
    monkeypatch.setattr(
        discogs,
        "_release_from_payload",
        lambda summary, detail: summary["title"],
    )
    monkeypatch.setattr(discogs, "_deduplicate_releases", lambda releases: releases)

    result = discogs.fetch_artist_releases(123, "token")

    assert result == ["Eigenes Album"]
