from musictagstudio.lyrics import LyricsDocument, LyricsLine, parse_lrc, render_lrc


def test_lrc_parses_metadata_multiple_timestamps_and_offset():
    document = parse_lrc(
        "[ar:Sido]\n[offset:100]\n[00:01.20][00:02.30]Maske\n"
    )

    assert document.metadata["ar"] == "Sido"
    assert document.plain_text == "Maske"
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


def test_plain_lrc_keeps_stanza_breaks():
    document = parse_lrc("Erste Strophe\n\nZweite Strophe\n")

    assert document.plain_text == "Erste Strophe\n\nZweite Strophe"
    assert parse_lrc(render_lrc(document)).plain_text == document.plain_text


def test_multiple_timestamps_do_not_duplicate_display_text():
    document = parse_lrc("[00:01.00][00:02.00]Refrain")

    assert len(document.synced_lines) == 2
    assert document.plain_text == "Refrain"


def test_instrumental_lrc_is_not_empty():
    document = parse_lrc("[instrumental:true]\n")

    assert document.instrumental is True
    assert document.is_empty is False
    assert "Instrumental" in document.display_text()
