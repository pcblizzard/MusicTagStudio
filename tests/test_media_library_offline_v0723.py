from pathlib import Path


def test_media_library_distinguishes_online_and_offline():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "media_library_widget.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "def set_library_index" in text
    assert '"Externe Quelle nicht erreichbar"' in text
    assert "local_online" in text
    assert "momentan nicht erreichbar" in text


def test_more_from_artist_does_not_depend_on_source_status():
    text = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(
        encoding="utf-8"
    )

    block = text.split(
        "def show_more_from_artist",
        1,
    )[1].split(
        "def _selected_album_keys",
        1,
    )[0]

    assert "source_online" not in block
    assert "search_artist" in block
