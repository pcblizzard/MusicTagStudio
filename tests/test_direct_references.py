import pytest

from musictagstudio.direct_references import (
    DirectAlbumReferenceError,
    parse_album_reference,
)


def test_apple_music_url():
    result = parse_album_reference(
        "https://music.apple.com/album/"
        "fenster-zum-hof/1775980788"
    )

    assert result.provider == "apple_music"
    assert result.reference_id == "1775980788"
    assert result.reference_type == "album"


def test_plain_apple_id():
    result = parse_album_reference(
        "1775980788"
    )

    assert result.provider == "apple_music"
    assert result.reference_id == "1775980788"


def test_musicbrainz_release_url():
    result = parse_album_reference(
        "https://musicbrainz.org/release/"
        "12345678-1234-1234-1234-123456789abc"
    )

    assert result.provider == "musicbrainz"
    assert result.reference_type == "release"


def test_musicbrainz_release_group_url():
    result = parse_album_reference(
        "https://musicbrainz.org/release-group/"
        "12345678-1234-1234-1234-123456789abc"
    )

    assert result.reference_type == "release-group"


def test_unsupported_url():
    with pytest.raises(
        DirectAlbumReferenceError
    ):
        parse_album_reference(
            "https://example.com/album/123"
        )
