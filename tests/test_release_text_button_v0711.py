from pathlib import Path

from musictagstudio.models.song import Song


def album_keys(
    songs,
    rows,
):
    return {
        (
            (
                songs[row].album_artist
                or songs[row].artist
            ).strip().casefold(),
            songs[row].album.strip().casefold(),
            str(
                Path(
                    songs[row].path
                ).parent.resolve()
            ).casefold(),
        )
        for row in rows
    }


def test_one_album_selection_enables_release_text():
    songs = [
        Song(
            artist="Artist",
            album_artist="Artist",
            album="Album",
            path="C:/Music/Artist/Album/01.flac",
        ),
        Song(
            artist="Artist",
            album_artist="Artist",
            album="Album",
            path="C:/Music/Artist/Album/02.flac",
        ),
    ]

    rows = [0, 1]
    enabled = (
        bool(rows)
        and len(
            album_keys(
                songs,
                rows,
            )
        )
        == 1
    )

    assert enabled is True


def test_multiple_albums_disable_release_text():
    songs = [
        Song(
            artist="Artist",
            album_artist="Artist",
            album="Album A",
            path="C:/Music/Artist/Album A/01.flac",
        ),
        Song(
            artist="Artist",
            album_artist="Artist",
            album="Album B",
            path="C:/Music/Artist/Album B/01.flac",
        ),
    ]

    rows = [0, 1]
    enabled = (
        bool(rows)
        and len(
            album_keys(
                songs,
                rows,
            )
        )
        == 1
    )

    assert enabled is False
