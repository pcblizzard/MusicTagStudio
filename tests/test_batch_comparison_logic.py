from musictagstudio.batch_comparison_logic import (
    BatchSongProposal,
    build_common_field_comparisons,
    build_track_field_comparisons,
)
from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song


def proposals():
    return [
        BatchSongProposal(
            song_row=0,
            song=Song(
                title="Track 1",
                album="Lokal",
                track="1",
            ),
            candidates=[
                MetadataCandidate(
                    source="apple_music",
                    confidence=90,
                    title="Apple 1",
                    album="Album X",
                    track="1",
                    total_tracks="2",
                ),
                MetadataCandidate(
                    source="musicbrainz",
                    confidence=85,
                    title="MB 1",
                    album="Album X",
                    label="Label X",
                ),
            ],
            warnings=[],
        ),
        BatchSongProposal(
            song_row=1,
            song=Song(
                title="Track 2",
                album="Lokal",
                track="2",
            ),
            candidates=[
                MetadataCandidate(
                    source="apple_music",
                    confidence=90,
                    title="Apple 2",
                    album="Album X",
                    track="2",
                    total_tracks="2",
                ),
                MetadataCandidate(
                    source="musicbrainz",
                    confidence=85,
                    title="MB 2",
                    album="Album X",
                    label="Label X",
                ),
            ],
            warnings=[],
        ),
    ]


def test_common_album_value_is_detected():
    comparisons = build_common_field_comparisons(
        proposals(),
        primary_source="apple_music",
        feature_handling="artist_only",
    )
    by_name = {
        item.field_name: item
        for item in comparisons
    }

    assert by_name["album"].values["apple_music"] == "Album X"
    assert by_name["album"].default_source == "apple_music"


def test_fallback_label_is_supplemented():
    comparisons = build_common_field_comparisons(
        proposals(),
        primary_source="apple_music",
        feature_handling="artist_only",
    )
    by_name = {
        item.field_name: item
        for item in comparisons
    }

    assert by_name["label"].values["musicbrainz"] == "Label X"
    assert by_name["label"].default_source == "musicbrainz"
    assert by_name["label"].is_supplemented


def test_track_fields_remain_individual():
    comparison = build_track_field_comparisons(
        proposals()[0],
        primary_source="apple_music",
        feature_handling="artist_only",
    )
    by_name = {
        item.field_name: item
        for item in comparison
    }

    assert by_name["title"].values["apple_music"] == "Apple 1"
    assert by_name["track"].values["apple_music"] == "1"
