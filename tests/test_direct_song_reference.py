from musictagstudio.direct_references import (
    parse_album_reference,
)


def test_apple_song_url_is_recognized():
    reference = parse_album_reference(
        "https://music.apple.com/us/song/minimum/1859696298"
    )

    assert reference.provider == "apple_music"
    assert reference.reference_type == "song"
    assert reference.reference_id == "1859696298"


def test_apple_album_url_remains_album():
    reference = parse_album_reference(
        "https://music.apple.com/us/album/deja-vu-1-2/1859696286"
    )

    assert reference.reference_type == "album"
