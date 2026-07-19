from pathlib import Path


def source() -> str:
    return (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(
        encoding="utf-8"
    )


def test_hardcoded_stieber_album_path_is_removed():
    text = source()

    assert "Stieber Twins - Fenster zum Hof" not in text
    assert "DEFAULT_MUSIC_FOLDER: str | None = None" in text


def test_source_scan_also_populates_tagger():
    text = source()

    assert '"songs": songs' in text
    assert "self._apply_songs_to_tagger" in text
    assert "self.scan_button.clicked.connect(self.rescan_library)" in text
