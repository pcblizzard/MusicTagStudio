from pathlib import Path


def test_tagger_exposes_single_track_lyrics_dialog():
    source = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert 'tr("show_lyrics"' in source  # i18n statt Fixtext
    assert "def _update_lyrics_button" in source
    assert "len(rows) == 1" in source
    assert "player_engine=self.player_bar.engine" in source
