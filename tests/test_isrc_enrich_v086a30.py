from __future__ import annotations

from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song
from musictagstudio.services.isrc_enrich import (
    enrich_song,
    merge_updates,
)


def _mb(**kw):
    return MetadataCandidate(source="musicbrainz", confidence=90, **kw)


def _dz(**kw):
    return MetadataCandidate(source="deezer", confidence=95, **kw)


def test_only_empty_fields_are_filled():
    song = Song(title="Song", artist="Artist", isrc="DEUM71203451")
    cand = _mb(title="Anderer Titel", genre="Rock", year="1999", label="XYZ")
    updates = merge_updates(song, [cand])
    # title/artist bleiben (vorhanden); nur leere Felder werden ergänzt.
    assert "title" not in updates
    assert "artist" not in updates
    assert updates == {"genre": "Rock", "year": "1999", "label": "XYZ"}


def test_first_candidate_with_value_wins():
    song = Song(title="S", artist="A", isrc="X")
    # MusicBrainz ohne Label, Deezer mit Label -> Deezer füllt.
    mb = _mb(genre="Pop")
    dz = _dz(genre="Elektro", label="Label Ltd")
    updates = merge_updates(song, [mb, dz])
    assert updates["genre"] == "Pop"  # MB zuerst
    assert updates["label"] == "Label Ltd"  # Deezer ergänzt


def test_enrich_song_without_isrc_is_noop():
    song = Song(title="S", artist="A", isrc="")
    called = []

    def lookup(isrc):
        called.append(isrc)
        return _mb(genre="Rock")

    result = enrich_song(song, lookups=(lookup,))
    assert result.updates == {}
    assert result.has_changes is False
    assert called == []  # ohne ISRC kein Lookup


def test_enrich_song_collects_from_lookups():
    song = Song(title="", artist="", isrc="DEUM71203451")

    def mb_lookup(isrc):
        assert isrc == "DEUM71203451"
        return _mb(title="Echt", artist="Künstler")

    def dz_lookup(isrc):
        return _dz(genre="Jazz", year="2001")

    result = enrich_song(song, lookups=(mb_lookup, dz_lookup))
    assert result.updates == {
        "title": "Echt",
        "artist": "Künstler",
        "genre": "Jazz",
        "year": "2001",
    }
    assert set(result.sources) == {"musicbrainz", "deezer"}


def test_failing_lookup_is_tolerated():
    song = Song(isrc="X")

    def boom(isrc):
        raise RuntimeError("Netzwerk weg")

    def ok(isrc):
        return _dz(genre="Rock")

    result = enrich_song(song, lookups=(boom, ok))
    assert result.updates == {"genre": "Rock"}
    assert result.sources == ("deezer",)


def test_no_hit_yields_no_changes():
    song = Song(isrc="X")
    result = enrich_song(song, lookups=(lambda i: None,))
    assert not result.has_changes
    assert result.sources == ()
