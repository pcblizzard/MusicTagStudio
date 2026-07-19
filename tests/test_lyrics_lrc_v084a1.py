from musictagstudio.lyrics import LyricsDocument, LyricsLine, parse_lrc, render_lrc


def test_lrc_parses_metadata_multiple_timestamps_and_offset():
    document = parse_lrc(
        "[ar:Sido]\n[offset:100]\n[00:01.20][00:02.30]Maske\n"
    )

    assert document.metadata["ar"] == "Sido"
    assert document.plain_text == "Maske\nMaske"
    assert document.synced_lines == (
        LyricsLine(1300, "Maske"),
        LyricsLine(2400, "Maske"),
    )


def test_lrc_round_trip_keeps_synced_lines():
    original = LyricsDocument(
        synced_lines=(LyricsLine(61_230, "Erste Zeile"),),
        metadata={"ar": "Künstler", "ti": "Titel"},
    )

    restored = parse_lrc(render_lrc(original))

    assert restored.synced_lines == (LyricsLine(61_230, "Erste Zeile"),)
    assert restored.metadata == original.metadata
