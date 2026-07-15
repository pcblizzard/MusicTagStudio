from musictagstudio.services.proposal import (
    _provider_order,
)


def test_disabled_enrichment_does_not_hide_sources():
    order = _provider_order(
        "apple_music",
        False,
    )

    assert order[0] == "apple_music"
    assert "musicbrainz" in order


def test_musicbrainz_can_be_preferred_without_hiding_apple():
    order = _provider_order(
        "musicbrainz",
        False,
    )

    assert order[0] == "musicbrainz"
    assert "apple_music" in order
