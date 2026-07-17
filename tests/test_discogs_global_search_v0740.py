from musictagstudio.media_library.discogs import (
    DiscogsCatalogHit,
    _search_rank,
)


def test_catalog_hit_supports_artist_release_and_label():
    hit = DiscogsCatalogHit(
        kind="label",
        entity_id=123,
        title="ersguterjunge",
    )

    assert hit.kind == "label"
    assert hit.entity_id == 123


def test_exact_catalog_title_ranks_first():
    assert (
        _search_rank(
            "Aggro Ansage Nr. 3",
            "Aggro Ansage Nr. 3",
        )
        < _search_rank(
            "Aggro Ansage Nr. 3",
            "Aggro Ansage Nr. 4",
        )
    )
