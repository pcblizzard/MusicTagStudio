from pathlib import Path


def test_tagger_exposes_single_track_lyrics_dialog():
    source = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert 'QPushButton("Lyrics anzeigen")' in source
    assert "def _update_lyrics_button" in source
    assert "len(rows) == 1" in source
    assert "LyricsDialog(self.songs[rows[0]], self)" in source
