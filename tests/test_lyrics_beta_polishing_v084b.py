from musictagstudio.lyrics import LyricsDocument, LyricsLine
from musictagstudio.ui.lyrics_dialog import (
    _document_display_text,
    _format_fetched_at,
    _source_display_name,
)


def test_source_names_are_user_facing():
    assert _source_display_name(LyricsDocument(source="LRC-Datei")).endswith(
        "Lokale LRC-Datei"
    )
    assert "lokal zwischengespeichert" in _source_display_name(
        LyricsDocument(source="LRCLIB")
    )


def test_fetched_timestamp_is_human_readable():
    value = _format_fetched_at("2026-07-20T10:30:00+00:00")

    assert "20.07.2026" in value
    assert "T" not in value


def test_timestamp_display_does_not_change_document():
    document = LyricsDocument(
        plain_text="Zeile",
        synced_lines=(LyricsLine(61_230, "Zeile"),),
    )

    assert _document_display_text(document, show_timestamps=True) == (
        "[01:01.23] Zeile"
    )
    assert document.plain_text == "Zeile"
