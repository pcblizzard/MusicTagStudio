from musictagstudio.core.normalizers import normalize_candidate
from musictagstudio.models.metadata import MetadataCandidate


def candidate() -> MetadataCandidate:
    return MetadataCandidate(
        source="apple_music",
        title="Titel [feat. Gast]",
        artist="Hauptkünstler",
    )


def test_artist_only_moves_feature_from_title():
    result = normalize_candidate(
        candidate(),
        feature_handling="artist_only",
    )

    assert result.title == "Titel"
    assert result.artist == "Hauptkünstler, Gast"


def test_title_and_artist_keeps_feature_in_title():
    result = normalize_candidate(
        candidate(),
        feature_handling="title_and_artist",
    )

    assert result.title == "Titel [feat. Gast]"
    assert result.artist == "Hauptkünstler, Gast"


def test_source_keeps_source_fields():
    result = normalize_candidate(
        candidate(),
        feature_handling="source",
    )

    assert result.title == "Titel [feat. Gast]"
    assert result.artist == "Hauptkünstler"
