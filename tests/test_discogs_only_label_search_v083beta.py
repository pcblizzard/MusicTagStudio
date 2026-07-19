from musictagstudio.media_library.discogs import DiscogsCatalogHit
from musictagstudio.ui import media_library_widget as widget


def test_exact_discogs_only_label_is_returned(monkeypatch):
    label = DiscogsCatalogHit(
        kind="label",
        entity_id=78015,
        title="ersguterjunge",
    )
    unrelated = DiscogsCatalogHit(
        kind="artist",
        entity_id=1,
        title="Junge (2)",
    )
    numbered_label = DiscogsCatalogHit(
        kind="label",
        entity_id=1313014,
        title="Ersguterjunge (2)",
    )
    monkeypatch.setattr(
        widget,
        "search_catalog",
        lambda *args, **kwargs: [unrelated, numbered_label, label],
    )

    assert widget._search_exact_discogs_catalog(
        "ersguterjunge", "token"
    ) == [label]


def test_album_title_can_match_discogs_artist_dash_title(monkeypatch):
    album = DiscogsCatalogHit(
        kind="master",
        entity_id=123,
        title="Clueso - Stadtrandlichter Live",
    )
    monkeypatch.setattr(
        widget,
        "search_catalog",
        lambda *args, **kwargs: [album],
    )

    assert widget._search_exact_discogs_catalog(
        "Stadtrandlichter Live", "token"
    ) == [album]
