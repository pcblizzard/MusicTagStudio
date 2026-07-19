from musictagstudio.media_library.discogs import DiscogsCatalogHit
from musictagstudio.ui import media_library_widget as widget


def hit(kind, entity_id, title):
    return DiscogsCatalogHit(kind=kind, entity_id=entity_id, title=title)


def test_exact_label_is_used_instead_of_similar_artist(monkeypatch):
    monkeypatch.setattr(
        widget,
        "search_catalog",
        lambda *args, **kwargs: [
            hit("artist", 2792029, "Aggro (5)"),
            hit("label", 25833, "Aggro Berlin"),
        ],
    )
    selected = []
    monkeypatch.setattr(
        widget,
        "fetch_label_releases",
        lambda entity_id, token, maximum, label_name: selected.append(
            (entity_id, label_name)
        ) or [],
    )
    monkeypatch.setattr(
        widget,
        "fetch_discogs_artist_releases",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    assert widget._fetch_discogs_catalog("Aggro Berlin", "token") == []
    assert selected == [(25833, "Aggro Berlin")]


def test_partial_artist_match_is_not_used_as_fallback(monkeypatch):
    monkeypatch.setattr(
        widget,
        "search_catalog",
        lambda *args, **kwargs: [hit("artist", 2792029, "Aggro (5)")],
    )
    monkeypatch.setattr(
        widget,
        "fetch_discogs_artist_releases",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    assert widget._fetch_discogs_catalog("Aggro Berlin", "token") == []
