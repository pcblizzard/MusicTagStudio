from musictagstudio.services.release_text import (
    _resolve_artist_folder,
)


def test_nearest_matching_artist_folder_is_used(
    tmp_path,
):
    artist = (
        tmp_path
        / "Music"
        / "Matthias Reim"
    )
    album = (
        artist
        / "MATTHIAS (XXL)"
    )
    album.mkdir(
        parents=True
    )

    result = _resolve_artist_folder(
        album,
        "Matthias Reim",
        2,
    )

    assert result == artist
