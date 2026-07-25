from __future__ import annotations

import json

from musictagstudio.providers import apple_music, apple_music_web


# Nachbau der echten music.apple.com-Suchseitenstruktur:
# root -> data[0] -> data -> sections -> items[*].contentDescriptor.
_ALBUM_ITEM = {
    "titleLinks": [
        {"title": "Das ist alles von der Kunstfreiheit gedeckt"}
    ],
    "subtitleLinks": [{"title": "Danger Dan"}],
    "trackCount": 11,
    "contentDescriptor": {
        "kind": "album",
        "url": (
            "https://music.apple.com/de/album/"
            "das-ist-alles-von-der-kunstfreiheit-gedeckt/1554122430?l=en-GB"
        ),
    },
}

_SONG_ITEM = {
    "title": "Das ist alles von der Kunstfreiheit gedeckt",
    "subtitle": "Song · Danger Dan",
    "contentDescriptor": {
        "kind": "song",
        "url": (
            "https://music.apple.com/de/album/"
            "das-ist-alles-von-der-kunstfreiheit-gedeckt/1554122430?i=1554122432"
        ),
    },
}

_PLAYLIST_ITEM = {
    "titleLinks": [{"title": "Pop Hits 2021"}],
    "contentDescriptor": {
        "kind": "playlist",
        "url": "https://music.apple.com/de/playlist/pop-hits-2021/pl.123",
    },
}


def _fixture_html() -> str:
    payload = {
        "data": [
            {
                "data": {
                    "sections": [
                        {
                            "id": "square-section - album",
                            "itemKind": "squareLockup",
                            "items": [_ALBUM_ITEM, _SONG_ITEM, _PLAYLIST_ITEM],
                        }
                    ]
                }
            }
        ]
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    return (
        "<html><head></head><body>"
        '<script type="application/json" id="serialized-server-data">'
        f"{serialized}</script></body></html>"
    )


def test_parse_search_albums_extracts_album_only():
    albums = apple_music_web.parse_search_albums(_fixture_html())

    # Nur der Album-Eintrag wird übernommen (Song und Playlist entfallen).
    assert len(albums) == 1
    album = albums[0]
    assert album.collection_id == "1554122430"
    assert album.album == "Das ist alles von der Kunstfreiheit gedeckt"
    assert album.artist == "Danger Dan"
    assert album.track_count == 11


def test_parse_search_albums_handles_missing_marker():
    assert apple_music_web.parse_search_albums("<html>nichts</html>") == []


def test_parse_search_albums_handles_broken_json():
    html = (
        '<script type="application/json" id="serialized-server-data">'
        "{kaputt</script>"
    )
    assert apple_music_web.parse_search_albums(html) == []


def test_plain_subtitle_extracts_artist_after_separator():
    assert apple_music_web._plain_subtitle("Song · Danger Dan") == "Danger Dan"
    assert apple_music_web._plain_subtitle("Danger Dan") == "Danger Dan"


def test_search_albums_web_uses_request_text(monkeypatch):
    captured = {}

    def fake_request_text(request, *, timeout):
        captured["url"] = request.full_url
        return _fixture_html()

    monkeypatch.setattr(
        apple_music_web, "request_text", fake_request_text
    )

    albums = apple_music_web.search_albums_web(
        "Das ist alles von der Kunstfreiheit gedeckt",
        "Danger Dan",
        country="DE",
    )

    assert [album.collection_id for album in albums] == ["1554122430"]
    assert "music.apple.com/de/search" in captured["url"]
    assert "term=" in captured["url"]


def test_search_albums_web_returns_empty_on_error(monkeypatch):
    def boom(request, *, timeout):
        raise apple_music_web.AppleRequestError("HTTP 503")

    monkeypatch.setattr(apple_music_web, "request_text", boom)

    assert apple_music_web.search_albums_web("Album", "Artist") == []


def test_variants_fall_back_to_web_when_api_empty(monkeypatch):
    # Die iTunes-Such-API liefert nichts (nicht indexiertes Album).
    monkeypatch.setattr(
        apple_music, "search_album", lambda *a, **k: []
    )
    monkeypatch.setattr(apple_music_web, "WEB_SEARCH_ENABLED", True)
    monkeypatch.setattr(
        apple_music_web,
        "search_albums_web",
        lambda *a, **k: [
            apple_music_web.AppleWebAlbum(
                collection_id="1554122430",
                album="Das ist alles von der Kunstfreiheit gedeckt",
                artist="Danger Dan",
                track_count=11,
            )
        ],
    )

    result = apple_music.search_album_variants(
        "Das ist alles von der Kunstfreiheit gedeckt",
        "Danger Dan",
        expected_track_count=11,
    )

    assert result, "the web fallback should surface the album"
    best = result[0]
    assert best.collection_id == "1554122430"
    assert best.confidence >= apple_music.MINIMUM_ALBUM_CONFIDENCE


def test_web_fallback_respects_disabled_flag(monkeypatch):
    monkeypatch.setattr(
        apple_music, "search_album", lambda *a, **k: []
    )
    monkeypatch.setattr(apple_music_web, "WEB_SEARCH_ENABLED", False)

    called = {"web": False}

    def fake_web(*a, **k):
        called["web"] = True
        return []

    monkeypatch.setattr(apple_music_web, "search_albums_web", fake_web)

    apple_music.search_album_variants("Album", "Artist")

    assert called["web"] is False, "disabled flag must skip the web search"


def test_settings_round_trip_for_web_search_flag(tmp_path):
    from musictagstudio.settings import AppSettings, load_settings, save_settings

    config = tmp_path / "config.toml"
    save_settings(AppSettings(apple_web_search_enabled=False), config)

    assert load_settings(config).apple_web_search_enabled is False


def test_apply_request_intervals_sets_web_flag(monkeypatch):
    from musictagstudio.settings import AppSettings, apply_request_intervals

    monkeypatch.setattr(apple_music_web, "WEB_SEARCH_ENABLED", True)
    apply_request_intervals(AppSettings(apple_web_search_enabled=False))

    assert apple_music_web.WEB_SEARCH_ENABLED is False


def test_proposal_web_helper_returns_confident_candidate(monkeypatch):
    from musictagstudio.providers.apple_music import AppleAlbumCandidate
    from musictagstudio.services import proposal

    monkeypatch.setattr(
        proposal,
        "search_albums_via_web",
        lambda *a, **k: [
            AppleAlbumCandidate(
                collection_id="1554122430",
                album="Das ist alles von der Kunstfreiheit gedeckt",
                artist="Danger Dan",
                track_count=11,
                year="2021",
                country="DE",
                confidence=95,
            )
        ],
    )

    candidate = proposal._apple_candidate_via_web_search(
        album_name="Das ist alles von der Kunstfreiheit gedeckt",
        album_artist="Danger Dan",
        wanted_year="2021",
        expected_track_count=11,
        store="DE",
    )

    assert candidate is not None
    assert candidate.collection_id == "1554122430"


def test_proposal_web_helper_skips_low_confidence(monkeypatch):
    from musictagstudio.providers.apple_music import AppleAlbumCandidate
    from musictagstudio.services import proposal

    monkeypatch.setattr(
        proposal,
        "search_albums_via_web",
        lambda *a, **k: [
            AppleAlbumCandidate(
                collection_id="999",
                album="Fremdes Album",
                artist="Andere",
                track_count=3,
                year="",
                country="DE",
                confidence=40,
            )
        ],
    )

    candidate = proposal._apple_candidate_via_web_search(
        album_name="Das ist alles von der Kunstfreiheit gedeckt",
        album_artist="Danger Dan",
        wanted_year="2021",
        expected_track_count=11,
        store="DE",
    )

    assert candidate is None
