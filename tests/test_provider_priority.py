from musictagstudio.core.merger import merge_metadata
from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song


def test_selected_provider_has_priority_for_all_fields():
    local = Song(title="Lokal")

    apple = MetadataCandidate(
        source="apple_music",
        confidence=80,
        title="Apple-Titel",
        isrc="APPLE-ISRC",
    )

    musicbrainz = MetadataCandidate(
        source="musicbrainz",
        confidence=95,
        title="MusicBrainz-Titel",
        isrc="MB-ISRC",
    )

    merged = merge_metadata(
        local,
        [apple, musicbrainz],
        primary_source="apple_music",
    )

    assert merged.values["title"] == "Apple-Titel"
    assert merged.values["isrc"] == "APPLE-ISRC"


def test_fallback_fills_missing_primary_field():
    local = Song()

    apple = MetadataCandidate(
        source="apple_music",
        confidence=90,
        title="Apple-Titel",
    )

    musicbrainz = MetadataCandidate(
        source="musicbrainz",
        confidence=80,
        isrc="MB-ISRC",
    )

    merged = merge_metadata(
        local,
        [apple, musicbrainz],
        primary_source="apple_music",
    )

    assert merged.values["title"] == "Apple-Titel"
    assert merged.values["isrc"] == "MB-ISRC"
