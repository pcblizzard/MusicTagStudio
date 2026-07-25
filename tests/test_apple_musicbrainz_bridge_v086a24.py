from musictagstudio import direct_album_lookup
from musictagstudio.providers.apple_music import AppleAlbumCandidate
from musictagstudio.providers.musicbrainz import MusicBrainzReleaseCandidate
from musictagstudio.services import proposal


APPLE_ALBUM_URL = (
    "https://music.apple.com/de/album/"
    "das-ist-alles-von-der-kunstfreiheit-gedeckt/1554122430"
)


def _relations_payload(url: str) -> dict:
    return {
        "relations": [
            {"type": "discogs", "url": {"resource": "https://www.discogs.com/x"}},
            {"type": "stream", "url": {"resource": url}},
        ]
    }


def test_bridge_extracts_collection_id(monkeypatch):
    monkeypatch.setattr(
        direct_album_lookup,
        "_get_json",
        lambda url: _relations_payload(APPLE_ALBUM_URL),
    )
    result = direct_album_lookup.apple_collection_id_from_musicbrainz_release(
        "mbid-1"
    )
    assert result == "1554122430"


def test_bridge_ignores_non_apple_relations(monkeypatch):
    monkeypatch.setattr(
        direct_album_lookup,
        "_get_json",
        lambda url: {
            "relations": [
                {"url": {"resource": "https://www.discogs.com/release/1"}},
            ]
        },
    )
    result = direct_album_lookup.apple_collection_id_from_musicbrainz_release(
        "mbid-1"
    )
    assert result is None


def test_bridge_handles_lookup_error(monkeypatch):
    def boom(url):
        raise direct_album_lookup.DirectAlbumLookupError("offline")

    monkeypatch.setattr(direct_album_lookup, "_get_json", boom)
    assert (
        direct_album_lookup.apple_collection_id_from_musicbrainz_release("x")
        is None
    )


def _release(confidence: int) -> MusicBrainzReleaseCandidate:
    return MusicBrainzReleaseCandidate(
        release_id="mbid-release",
        album="Das ist alles von der Kunstfreiheit gedeckt",
        artist="Danger Dan",
        track_count=11,
        year="2021",
        status="Official",
        country="DE",
        confidence=confidence,
    )


def test_candidate_via_musicbrainz_uses_bridge(monkeypatch):
    monkeypatch.setattr(
        proposal,
        "search_mb_release",
        lambda *a, **kw: [_release(92)],
    )
    monkeypatch.setattr(
        proposal,
        "apple_collection_id_from_musicbrainz_release",
        lambda release_id: "1554122430",
    )

    candidate = proposal._apple_candidate_via_musicbrainz(
        album_name="Das ist alles von der Kunstfreiheit gedeckt",
        album_artist="Danger Dan",
        wanted_year="2021",
        expected_track_count=11,
        store="DE",
    )

    assert isinstance(candidate, AppleAlbumCandidate)
    assert candidate.collection_id == "1554122430"
    assert candidate.country == "DE"


def test_candidate_via_musicbrainz_skips_low_confidence(monkeypatch):
    monkeypatch.setattr(
        proposal,
        "search_mb_release",
        lambda *a, **kw: [_release(40)],
    )
    called = {"bridge": 0}

    def bridge(release_id):
        called["bridge"] += 1
        return "1554122430"

    monkeypatch.setattr(
        proposal,
        "apple_collection_id_from_musicbrainz_release",
        bridge,
    )

    candidate = proposal._apple_candidate_via_musicbrainz(
        album_name="Album",
        album_artist="Artist",
        wanted_year="2021",
        expected_track_count=11,
        store="DE",
    )

    assert candidate is None
    assert called["bridge"] == 0
