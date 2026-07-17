from pathlib import Path


def test_discogs_module_contains_label_and_catalog_endpoints():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "media_library"
        / "discogs.py"
    ).read_text(
        encoding="utf-8"
    )

    assert '"/database/search"' in text
    assert 'f"/labels/{label_id}/releases"' in text
    assert 'f"/masters/{entity_id}"' in text
    assert 'f"/releases/{entity_id}"' in text
