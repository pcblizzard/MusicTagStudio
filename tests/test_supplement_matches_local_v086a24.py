from musictagstudio.batch_comparison_logic import (
    BatchSongProposal,
    build_common_field_comparisons,
)
from musictagstudio.comparison_logic import (
    build_field_comparisons,
    choose_default_source,
)
from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song


def _mb_label(label: str) -> MetadataCandidate:
    return MetadataCandidate(
        source="musicbrainz",
        confidence=85,
        album="Album X",
        label=label,
    )


def test_common_label_not_supplemented_when_matching_local():
    # Apple (primary) has no label; MusicBrainz repeats the local value.
    proposals = [
        BatchSongProposal(
            song_row=row,
            song=Song(title=f"T{row}", album="Album X", label="Antilopen"),
            candidates=[_mb_label("Antilopen")],
            warnings=[],
        )
        for row in range(2)
    ]
    by_name = {
        item.field_name: item
        for item in build_common_field_comparisons(
            proposals,
            primary_source="apple_music",
            feature_handling="artist_only",
        )
    }
    assert by_name["label"].values["local"] == "Antilopen"
    assert by_name["label"].values["musicbrainz"] == "Antilopen"
    assert by_name["label"].is_supplemented is False


def test_common_label_supplemented_when_local_empty():
    proposals = [
        BatchSongProposal(
            song_row=0,
            song=Song(title="T", album="Album X"),
            candidates=[_mb_label("Antilopen")],
            warnings=[],
        )
    ]
    by_name = {
        item.field_name: item
        for item in build_common_field_comparisons(
            proposals,
            primary_source="apple_music",
            feature_handling="artist_only",
        )
    }
    assert by_name["label"].is_supplemented is True


def test_track_field_not_supplemented_when_matching_local():
    song = Song(title="T", album="Album X", track="1", label="Antilopen")
    by_name = {
        item.field_name: item
        for item in build_field_comparisons(
            song,
            [_mb_label("Antilopen")],
            primary_source="apple_music",
            feature_handling="artist_only",
        )
    }
    assert by_name["label"].is_supplemented is False
    # The selector defaults to local, not to a no-op provider choice.
    assert by_name["label"].default_source == "local"


def test_default_source_prefers_local_over_matching_fallback():
    # Primary (apple) empty, fallback (mb) equals local -> keep local.
    values = {"local": "Antilopen", "apple_music": "", "musicbrainz": "Antilopen"}
    assert choose_default_source(values, primary_source="apple_music") == "local"


def test_default_source_uses_fallback_that_differs():
    values = {"local": "Antilopen", "apple_music": "", "musicbrainz": "JKP"}
    assert (
        choose_default_source(values, primary_source="apple_music")
        == "musicbrainz"
    )
