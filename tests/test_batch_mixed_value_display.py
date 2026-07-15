from musictagstudio.batch_comparison_logic import (
    BatchSongProposal,
    build_common_field_comparisons,
)
from musictagstudio.models.metadata import (
    MetadataCandidate,
)
from musictagstudio.models.song import Song


def test_mixed_musicbrainz_values_are_visible():
    proposals = [
        BatchSongProposal(
            song_row=0,
            song=Song(
                title="A",
                album="Album",
            ),
            candidates=[
                MetadataCandidate(
                    source="musicbrainz",
                    title="A",
                    album="Album",
                    year="1997",
                )
            ],
            warnings=[],
        ),
        BatchSongProposal(
            song_row=1,
            song=Song(
                title="B",
                album="Album",
            ),
            candidates=[
                MetadataCandidate(
                    source="musicbrainz",
                    title="B",
                    album="Album",
                    year="2024",
                )
            ],
            warnings=[],
        ),
        BatchSongProposal(
            song_row=2,
            song=Song(
                title="C",
                album="Album",
            ),
            candidates=[
                MetadataCandidate(
                    source="musicbrainz",
                    title="C",
                    album="Album",
                    year="1997",
                )
            ],
            warnings=[],
        ),
    ]

    comparisons = (
        build_common_field_comparisons(
            proposals,
            primary_source="apple_music",
            feature_handling="artist_only",
        )
    )
    year = next(
        item
        for item in comparisons
        if item.field_name == "year"
    )

    assert (
        year.values["musicbrainz"]
        == "<verschiedene Werte>"
    )
    assert (
        year.display_values[
            "musicbrainz"
        ]
        == "1997 (2×), 2024 (1×)"
    )
