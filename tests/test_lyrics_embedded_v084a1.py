from musictagstudio.lyrics.embedded import (
    lyrics_from_tags,
    lyrics_variants_from_tags,
)


class TextFrame:
    def __init__(self, text):
        self.text = text


def test_embedded_id3_unsynchronised_lyrics_are_read():
    document = lyrics_from_tags({"USLT::deu": TextFrame("Hallo Welt")})

    assert document is not None
    assert document.plain_text == "Hallo Welt"
    assert document.source == "Eingebettete Lyrics"


def test_embedded_vorbis_synced_lyrics_are_parsed():
    document = lyrics_from_tags(
        {"SYNCEDLYRICS": ["[00:01.00]Hallo", "[00:02.00]Welt"]}
    )

    assert document is not None
    assert [line.time_ms for line in document.synced_lines] == [1000, 2000]


def test_multiple_embedded_languages_remain_selectable():
    variants = lyrics_variants_from_tags(
        {
            "USLT::deu": TextFrame("Deutscher Text"),
            "USLT::eng": TextFrame("English lyrics"),
        }
    )

    assert [item.plain_text for item in variants] == [
        "Deutscher Text",
        "English lyrics",
    ]
    assert "USLT::deu" in variants[0].source
