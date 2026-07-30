from __future__ import annotations

from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song
from musictagstudio.services.auto_tag import (
    REASON_LOW_CONFIDENCE,
    REASON_NO_CHANGES,
    REASON_NO_MATCH,
    candidate_updates,
    decide,
    run_auto_tag,
    select_candidate,
    summarize,
)
from musictagstudio.services.proposal import ProposalResult


def _result(candidates):
    return ProposalResult(
        merged=None, candidates=list(candidates), warnings=[], sources={}
    )


def _cand(source, conf, **fields):
    return MetadataCandidate(source=source, confidence=conf, **fields)


def test_select_highest_confidence():
    result = _result([_cand("apple_music", 70, title="A"),
                      _cand("musicbrainz", 95, title="B")])
    assert select_candidate(result, primary_source="apple_music").confidence == 95


def test_select_prefers_primary_on_tie():
    result = _result([_cand("apple_music", 90, title="A"),
                      _cand("musicbrainz", 90, title="B")])
    chosen = select_candidate(result, primary_source="musicbrainz")
    assert chosen.source == "musicbrainz"


def test_candidate_updates_only_changed_nonempty():
    song = Song(title="Old", artist="X", album="")
    cand = _cand("apple_music", 95, title="New", artist="X", album="Alb", genre="")
    updates = candidate_updates(cand, song)
    assert updates == {"title": "New", "album": "Alb"}


def test_high_confidence_applies():
    song = Song(title="Old", path="a.flac")
    result = _result([_cand("apple_music", 96, title="New")])
    d = decide(result, song, primary_source="apple_music", threshold=90)
    assert d.applied and d.updates == {"title": "New"} and d.reason == ""


def test_low_confidence_goes_to_review_with_updates():
    song = Song(title="Old", path="a.flac")
    result = _result([_cand("apple_music", 80, title="New")])
    d = decide(result, song, primary_source="apple_music", threshold=90)
    assert not d.applied
    assert d.reason == REASON_LOW_CONFIDENCE
    assert d.updates == {"title": "New"}  # Vorschlag bleibt für die Prüfung


def test_no_match():
    d = decide(_result([]), Song(path="a.flac"), primary_source="apple_music")
    assert not d.applied and d.reason == REASON_NO_MATCH


def test_no_changes_when_candidate_matches_song():
    song = Song(title="Same", artist="X", path="a.flac")
    result = _result([_cand("apple_music", 99, title="Same", artist="X")])
    d = decide(result, song, primary_source="apple_music")
    assert not d.applied and d.reason == REASON_NO_CHANGES


def test_summarize_counts():
    songs = [Song(title="a", path="1"), Song(title="b", path="2"),
             Song(title="c", path="3")]
    results = [
        _result([_cand("apple_music", 95, title="A")]),   # applied
        _result([_cand("apple_music", 60, title="B")]),   # review
        _result([]),                                      # no match
    ]
    decisions = run_auto_tag(songs, results, primary_source="apple_music",
                             threshold=90)
    assert summarize(decisions) == (1, 1, 1)
