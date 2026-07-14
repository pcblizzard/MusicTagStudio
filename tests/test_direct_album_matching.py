from musictagstudio.direct_album_lookup import (
    DirectAlbumResult,
    DirectAlbumTrack,
    match_album_tracks,
)
from musictagstudio.models.song import Song


def album():
    return DirectAlbumResult(
        provider="apple_music",
        album="Album",
        album_artist="Artist",
        tracks=(
            DirectAlbumTrack(
                title="Erster Titel",
                artist="Artist",
                album_artist="Artist",
                album="Album",
                genre="",
                year="2020",
                track="1",
                total_tracks="2",
                disc="1",
                total_discs="1",
            ),
            DirectAlbumTrack(
                title="Zweiter Titel",
                artist="Artist",
                album_artist="Artist",
                album="Album",
                genre="",
                year="2020",
                track="2",
                total_tracks="2",
                disc="1",
                total_discs="1",
            ),
        ),
    )


def test_matches_by_track_number():
    songs = [
        Song(
            title="Falsch geschrieben",
            track="1",
            disc="1",
        ),
        Song(
            title="Auch falsch",
            track="2",
            disc="1",
        ),
    ]

    result = match_album_tracks(
        songs,
        album(),
    )

    assert result[0].title == "Erster Titel"
    assert result[1].title == "Zweiter Titel"


def test_falls_back_to_title():
    songs = [
        Song(
            title="Zweiter Titel",
            track="",
            disc="",
        )
    ]

    result = match_album_tracks(
        songs,
        album(),
    )

    assert result[0].track == "2"
