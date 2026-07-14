from musictagstudio.comparison_logic import (
    build_field_comparisons,
    choose_default_source,
)
from musictagstudio.models.metadata import (
    MetadataCandidate,
)
from musictagstudio.models.song import Song


def test_primary_source_is_default():
    values = {
        "local": "Lokal",
        "apple_music": "Apple",
        "musicbrainz": "MB",
    }

    assert (
        choose_default_source(
            values,
            primary_source="musicbrainz",
        )
        == "musicbrainz"
    )


def test_fallback_is_used_when_primary_is_empty():
    values = {
        "local": "Lokal",
        "apple_music": "Apple",
        "musicbrainz": "",
    }

    assert (
        choose_default_source(
            values,
            primary_source="musicbrainz",
        )
        == "apple_music"
    )


def test_conflict_and_supplement_are_detected():
    song = Song(
        title="Lokal",
        label="",
    )
    apple = MetadataCandidate(
        source="apple_music",
        confidence=90,
        title="Apple-Titel",
        label="",
    )
    musicbrainz = MetadataCandidate(
        source="musicbrainz",
        confidence=85,
        title="MB-Titel",
        label="Label X",
    )

    comparisons = build_field_comparisons(
        song,
        [apple, musicbrainz],
        primary_source="apple_music",
        feature_handling="artist_only",
    )

    by_name = {
        comparison.field_name: comparison
        for comparison in comparisons
    }

    assert by_name["title"].has_conflict
    assert (
        by_name["title"].default_source
        == "apple_music"
    )

    assert by_name["label"].is_supplemented
    assert (
        by_name["label"].default_source
        == "musicbrainz"
    )
