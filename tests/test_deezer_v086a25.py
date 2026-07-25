from __future__ import annotations

import pytest

from musictagstudio.providers import deezer


_ALBUM_SEARCH = {
    "data": [
        {
            "id": 222313582,
            "title": "Das ist alles von der Kunstfreiheit gedeckt",
            "nb_tracks": 11,
            "artist": {"name": "Danger Dan"},
        },
        {
            "id": 437452327,
            "title": "Das ist alles von der Kunstfreiheit gedeckt (Live)",
            "nb_tracks": 16,
            "artist": {"name": "Danger Dan"},
        },
    ]
}

_ALBUM_DETAIL = {
    "title": "Das ist alles von der Kunstfreiheit gedeckt",
    "artist": {"name": "Danger Dan"},
    "label": "Antilopen Geldwaesche/WM Germany",
    "release_date": "2021-04-30",
    "genres": {"data": [{"name": "Pop"}]},
}

_ALBUM_TRACKS = {
    "data": [
        {
            "id": 1,
            "title": "Lauf davon",
            "track_position": 1,
            "disk_number": 1,
            "isrc": "DEUI32100001",
            "duration": 251,
            "artist": {"name": "Danger Dan"},
        },
        {
            "id": 2,
            "title": "Das ist alles von der Kunstfreiheit gedeckt",
            "track_position": 2,
            "disk_number": 1,
            "isrc": "DEUI32100002",
            "duration": 228,
            "artist": {"name": "Danger Dan"},
        },
    ]
}


def _route(monkeypatch, mapping):
    def fake_get_json(url):
        for needle, payload in mapping.items():
            if needle in url:
                return payload
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(deezer, "_get_json", fake_get_json)


def test_search_albums_scores_exact_match_highest(monkeypatch):
    _route(monkeypatch, {"/search/album": _ALBUM_SEARCH})

    results = deezer.search_albums(
        "Das ist alles von der Kunstfreiheit gedeckt",
        "Danger Dan",
        expected_track_count=11,
    )

    assert results[0].album_id == "222313582"
    assert results[0].confidence >= deezer.MINIMUM_ALBUM_CONFIDENCE
    # Die Live-Version mit abweichender Trackzahl rankt niedriger.
    assert results[0].confidence > results[1].confidence


def test_lookup_album_builds_tracklist_with_isrc(monkeypatch):
    _route(
        monkeypatch,
        {
            "/album/222313582/tracks": _ALBUM_TRACKS,
            "/album/222313582": _ALBUM_DETAIL,
        },
    )

    result = deezer.lookup_album("222313582")

    assert result.provider == "deezer"
    assert result.album_artist == "Danger Dan"
    assert len(result.tracks) == 2
    second = result.tracks[1]
    assert second.track == "2"
    assert second.disc == "1"
    assert second.total_tracks == "2"
    assert second.isrc == "DEUI32100002"
    assert second.label == "Antilopen Geldwaesche/WM Germany"
    assert second.year == "2021"
    assert second.genre == "Pop"
    assert second.duration_ms == 228000


def test_lookup_album_raises_without_tracks(monkeypatch):
    _route(
        monkeypatch,
        {
            "/album/1/tracks": {"data": []},
            "/album/1": _ALBUM_DETAIL,
        },
    )

    with pytest.raises(deezer.DeezerProviderError):
        deezer.lookup_album("1")


def test_search_song_returns_scored_candidates(monkeypatch):
    _route(
        monkeypatch,
        {
            "/search": {
                "data": [
                    {
                        "id": 5,
                        "title": "Lauf davon",
                        "duration": 251,
                        "artist": {"name": "Danger Dan"},
                        "album": {"id": 9, "title": "Album"},
                    }
                ]
            }
        },
    )

    results = deezer.search_song("Lauf davon", "Danger Dan", "Album")

    assert results
    assert results[0].source == "deezer"
    assert results[0].title == "Lauf davon"
    assert results[0].release_id == "9"


def test_search_albums_empty_on_error(monkeypatch):
    def boom(url):
        raise deezer.DeezerProviderError("offline")

    monkeypatch.setattr(deezer, "_get_json", boom)

    assert deezer.search_albums("Album", "Artist") == []


def test_add_album_aware_deezer_candidates(monkeypatch):
    from musictagstudio.models.song import Song
    from musictagstudio.services import proposal

    monkeypatch.setattr(
        proposal.deezer,
        "search_albums",
        lambda *a, **k: [
            deezer.DeezerAlbumCandidate(
                album_id="222313582",
                album="Album X",
                artist="Danger Dan",
                track_count=2,
                confidence=100,
            )
        ],
    )
    _route(
        monkeypatch,
        {
            "/album/222313582/tracks": _ALBUM_TRACKS,
            "/album/222313582": _ALBUM_DETAIL,
        },
    )

    songs = [
        Song(title="Lauf davon", artist="Danger Dan", album="Album X",
             track="1", path="C:/m/01.flac"),
        Song(
            title="Das ist alles von der Kunstfreiheit gedeckt",
            artist="Danger Dan", album="Album X", track="2",
            path="C:/m/02.flac",
        ),
    ]
    candidates: list[list] = [[], []]
    warnings: list[list] = [[], []]

    resolved = proposal._add_album_aware_deezer_candidates(
        songs, candidates, warnings
    )

    assert resolved == {0, 1}
    assert all(
        any(c.source == "deezer" for c in row) for row in candidates
    )
    # ISRC aus Deezer landet im zugeordneten Kandidaten.
    deezer_cand = next(c for c in candidates[1] if c.source == "deezer")
    assert deezer_cand.isrc == "DEUI32100002"
