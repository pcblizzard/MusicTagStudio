from pathlib import Path


def source_text() -> str:
    return (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")


def test_table_uses_two_digit_number_pair_formatter():
    text = source_text()

    assert "def _format_number_pair" in text
    assert 'return f"{int(text):02d}"' in text
    assert "song.track," in text
    assert "song.total_tracks," in text
