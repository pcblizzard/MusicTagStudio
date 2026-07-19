from musictagstudio.media_library import discogs
from musictagstudio.media_library.discogs import DiscogsRelease


def test_catalog_snapshot_roundtrip(monkeypatch, tmp_path):
    cache_path = tmp_path / "discogs.sqlite3"
    monkeypatch.setattr(discogs, "_catalog_cache_path", lambda: cache_path)
    release = DiscogsRelease(
        source_id="discogs:561408",
        release_id=561408,
        title="Maske",
        labels=("Aggro Berlin",),
        formats=("CD", "Album"),
    )

    live = discogs.save_catalog_snapshot("Aggro Berlin", [release])
    cached = discogs.load_catalog_snapshot("Aggro Berlin")

    assert live.from_cache is False
    assert cached is not None
    assert cached.from_cache is True
    assert cached.releases == (release,)


def test_cache_key_is_case_and_punctuation_insensitive(monkeypatch, tmp_path):
    monkeypatch.setattr(
        discogs, "_catalog_cache_path", lambda: tmp_path / "discogs.sqlite3"
    )
    discogs.save_catalog_snapshot("Aggro Berlin", [])

    assert discogs.load_catalog_snapshot("AGGRO-BERLIN") is not None
