from pathlib import Path


def media_source() -> str:
    return (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "media_library_widget.py"
    ).read_text(
        encoding="utf-8"
    )


def test_category_arrow_is_in_release_column():
    text = media_source()

    assert '"Veröffentlichung"' in text
    assert 'f"{category} ({len(entries)})"' in text
    assert "parent.setIcon" in text


def test_edition_cover_and_cache_are_present():
    text = media_source()

    assert "self.cover_label" in text
    assert "def _fetch_release_cover" in text
    assert "cache/media_library/covers" not in text
    assert '"media_library"' in text
    assert '"covers"' in text
    assert "front-250" in text


def test_public_artist_search_exists():
    assert "def search_artist" in media_source()
