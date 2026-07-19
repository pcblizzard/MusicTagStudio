from musictagstudio.media_library.discogs import DiscogsCatalogHit
from musictagstudio.ui import media_library_widget as widget


def hit(title="Mark Forster - Bauch und Kopf Live", year="2015"):
    return DiscogsCatalogHit(
        kind="release",
        entity_id=123,
        title=title,
        thumb="https://example.test/cover.jpg",
        year=year,
    )


def test_discogs_cover_is_used_after_missing_musicbrainz_cover(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(widget, "_fetch_release_cover", lambda *_args: None)
    monkeypatch.setattr(widget, "search_catalog", lambda *_args, **_kwargs: [hit()])
    monkeypatch.setattr(widget, "_fetch_url_cover", lambda *_args: b"cover")

    data = widget._fetch_release_cover_with_discogs(
        "mb-release",
        tmp_path,
        "Mark Forster",
        "Bauch und Kopf Live",
        "2015",
        "token",
    )

    assert data == b"cover"


def test_discogs_cover_rejects_wrong_artist_or_year(monkeypatch, tmp_path):
    monkeypatch.setattr(widget, "_fetch_release_cover", lambda *_args: None)
    monkeypatch.setattr(
        widget,
        "search_catalog",
        lambda *_args, **_kwargs: [hit("Andere Band - Bauch und Kopf Live", "2014")],
    )

    data = widget._fetch_release_cover_with_discogs(
        "mb-release",
        tmp_path,
        "Mark Forster",
        "Bauch und Kopf Live",
        "2015",
        "token",
    )

    assert data is None
