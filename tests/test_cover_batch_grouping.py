from musictagstudio.cover_management.manager import (
    CoverManager,
)
from musictagstudio.models.song import Song


def test_group_songs_by_album():
    songs = [
        Song(
            title="A",
            album="Album 1",
            album_artist="Artist",
            path="C:/Music/Artist/Album 1/a.flac",
        ),
        Song(
            title="B",
            album="Album 1",
            album_artist="Artist",
            path="C:/Music/Artist/Album 1/b.flac",
        ),
        Song(
            title="C",
            album="Album 2",
            album_artist="Artist",
            path="C:/Music/Artist/Album 2/c.flac",
        ),
    ]

    grouped = CoverManager.group_songs_by_album(
        songs
    )

    assert len(grouped) == 2
    assert sorted(
        len(items)
        for items in grouped.values()
    ) == [1, 2]
