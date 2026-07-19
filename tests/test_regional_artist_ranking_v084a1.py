from musictagstudio.media_library.controller import CatalogSearchController
from musictagstudio.media_library.service import ArtistCandidate


def test_equally_named_artist_from_preferred_country_ranks_first():
    artists = [
        ArtistCandidate("it", "Mark Foster", country="IT", score=100),
        ArtistCandidate("de", "Mark Foster", country="DE", score=80),
        ArtistCandidate("us", "Mark Foster", country="US", score=90),
    ]

    ranked = CatalogSearchController._rank_candidates(
        "Mark Foster",
        artists,
        preferred_country="DE",
    )

    assert [artist.artist_id for artist in ranked] == ["de", "it", "us"]


def test_regional_preference_does_not_hide_other_countries():
    artists = [
        ArtistCandidate("gb", "Mark Knopfler", country="GB", score=100),
        ArtistCandidate("de", "Mark Foster", country="DE", score=80),
    ]

    ranked = CatalogSearchController._rank_candidates(
        "Mark Knopfler",
        artists,
        preferred_country="DE",
    )

    assert ranked[0].artist_id == "gb"
    assert len(ranked) == 2


def test_regional_preference_can_compensate_for_one_letter_typo():
    artists = [
        ArtistCandidate("it", "Mark Foster", country="IT", score=100),
        ArtistCandidate("de", "Mark Forster", country="DE", score=80),
    ]

    ranked = CatalogSearchController._rank_candidates(
        "Mark Foster",
        artists,
        preferred_country="DE",
    )

    assert ranked[0].artist_id == "de"
