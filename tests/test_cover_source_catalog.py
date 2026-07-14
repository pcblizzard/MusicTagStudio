from musictagstudio.cover_source_catalog import COVER_SOURCES_BY_ID

def test_supported_cover_sources():
    assert COVER_SOURCES_BY_ID['apple_music'].selectable
    assert COVER_SOURCES_BY_ID['cover_art_archive'].selectable
    assert not COVER_SOURCES_BY_ID['amazon_music'].selectable
