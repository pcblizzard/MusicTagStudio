from __future__ import annotations

from musictagstudio.providers import musicbrainz


_RECORDING = {
    "id": "mbid-1",
    "title": "Lauf davon",
    "length": 251000,
    "artist-credit": [{"artist": {"name": "Danger Dan"}}],
    "isrcs": ["DEUI32100001"],
    "releases": [
        {
            "id": "rel-1",
            "title": "Das ist alles von der Kunstfreiheit gedeckt",
            "date": "2021-04-30",
            "artist-credit": [{"artist": {"name": "Danger Dan"}}],
            "media": [
                {
                    "position": 1,
                    "track-count": 11,
                    "tracks": [
                        {"id": "trk-1", "number": "1", "position": 1}
                    ],
                }
            ],
        }
    ],
}


def test_lookup_recording_by_id_builds_candidate(monkeypatch):
    monkeypatch.setattr(
        musicbrainz, "_request_json", lambda url: _RECORDING
    )

    candidate = musicbrainz.lookup_recording_by_id("mbid-1")

    assert candidate is not None
    assert candidate.source == "musicbrainz"
    assert candidate.title == "Lauf davon"
    assert candidate.artist == "Danger Dan"
    assert candidate.album == "Das ist alles von der Kunstfreiheit gedeckt"
    assert candidate.year == "2021"
    assert candidate.isrc == "DEUI32100001"
    assert candidate.external_id == "mbid-1"


def test_lookup_recording_by_id_empty_id_returns_none():
    assert musicbrainz.lookup_recording_by_id("   ") is None


def test_lookup_recording_by_id_missing_payload(monkeypatch):
    monkeypatch.setattr(musicbrainz, "_request_json", lambda url: {})
    assert musicbrainz.lookup_recording_by_id("mbid-x") is None
