from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song
from musictagstudio.services import proposal


ALBUM = "Das ist alles von der Kunstfreiheit gedeckt"


def _song() -> Song:
    return Song(
        title=ALBUM,
        artist="Danger Dan",
        album_artist="Danger Dan",
        album=ALBUM,
        track="2",
        total_tracks="11",
        disc="1",
        path="C:/Album/2.flac",
    )


def _compilation_hit() -> MetadataCandidate:
    # Same title + artist, but a different release (benefit compilation)
    # where the song is track 3 of 24.
    return MetadataCandidate(
        source="apple_music",
        confidence=88,
        title=ALBUM,
        artist="Danger Dan",
        album_artist="Danger Dan",
        album="Seenotrettung ist kein Verbrechen",
        track="3",
        total_tracks="24",
        disc="1",
        total_discs="1",
        external_id="song-comp-3",
        release_id="1639490294",
    )


def _patch(monkeypatch, hit: MetadataCandidate) -> None:
    monkeypatch.setattr(
        proposal,
        "search_apple",
        lambda *a, **kw: [hit],
    )
    monkeypatch.setattr(proposal, "_local_duration_ms", lambda p: None)
    monkeypatch.setattr(proposal, "_title_from_filename", lambda p: "")


def test_cross_release_hit_drops_track_and_disc(monkeypatch):
    _patch(monkeypatch, _compilation_hit())
    candidates: list[MetadataCandidate] = []
    warnings: list[str] = []

    proposal._add_safe_single_apple_candidate(
        _song(),
        candidates,
        warnings,
        country="DE",
    )

    assert len(candidates) == 1
    accepted = candidates[0]
    # The wrong compilation track number must not leak in.
    assert accepted.track == ""
    assert accepted.disc == ""
    assert accepted.total_tracks == ""
    # Non-positional metadata is still available for enrichment.
    assert accepted.title == ALBUM
    assert accepted.artist == "Danger Dan"


def test_matching_album_keeps_track_and_disc(monkeypatch):
    hit = MetadataCandidate(
        source="apple_music",
        confidence=95,
        title=ALBUM,
        artist="Danger Dan",
        album_artist="Danger Dan",
        album=ALBUM,
        track="2",
        total_tracks="11",
        disc="1",
        external_id="song-real-2",
        release_id="1554122430",
    )
    _patch(monkeypatch, hit)
    candidates: list[MetadataCandidate] = []

    proposal._add_safe_single_apple_candidate(
        _song(),
        candidates,
        [],
        country="DE",
    )

    assert len(candidates) == 1
    assert candidates[0].track == "2"
    assert candidates[0].disc == "1"


def test_pure_helper_only_strips_on_mismatch():
    hit = _compilation_hit()
    stripped = proposal._without_cross_release_position(
        hit,
        wanted_album=ALBUM,
    )
    assert stripped.track == "" and stripped.disc == ""

    same = proposal._without_cross_release_position(
        hit,
        wanted_album="Seenotrettung ist kein Verbrechen",
    )
    assert same.track == "3"
