from pathlib import Path


def source() -> str:
    return (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "media_library_widget.py"
    ).read_text(encoding="utf-8")


def test_search_is_single_musicbrainz_artist_search():
    text = source()

    assert "self.search_mode_combo" not in text
    assert '"Discogs ergänzen"' not in text
    assert '"Discogs-Token fehlt"' not in text
    assert "search_catalog" not in text
    assert "search_artists" in text
    assert 'tr("search_artist_placeholder", self.language)' in text


def test_views_remain_available():
    text = source()

    for label in (
        '"Discografie"',
        '"Tabelle"',
        '"Coverraster"',
        '"Cover + Liste"',
    ):
        assert label in text


def test_removed_discogs_modes_and_release_filter_stay_absent():
    text = source()

    assert '"Discogs ergänzen"' not in text
    assert "self.search_mode_combo" not in text
    assert '"Veröffentlichungen filtern:"' not in text
    assert "self.release_filter_edit" not in text
    assert "def _apply_release_filter" not in text
