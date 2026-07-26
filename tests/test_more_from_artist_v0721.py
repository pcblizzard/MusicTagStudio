from pathlib import Path


def test_tagger_has_bidirectional_artist_navigation():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(
        encoding="utf-8"
    )

    assert 'tr("more_artist"' in text  # i18n statt Fixtext
    assert "def show_more_from_artist" in text
    assert "self.media_library.search_artist" in text
    assert 'addMenu(\n            "Audio-Analyse"' not in text
    assert 'addMenu(\n            "Bibliotheksprüfung"' not in text
    assert 'addMenu(\n            "Einstellungen"' not in text
