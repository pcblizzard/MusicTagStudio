from musictagstudio.direct_album_lookup import (
    DirectAlbumResult,
    DirectAlbumTrack,
    match_album_tracks,
)
from musictagstudio.models.song import Song


def album_track(
    title: str,
    track: str,
) -> DirectAlbumTrack:
    return DirectAlbumTrack(
        title=title,
        artist="Stieber Twins",
        album_artist="Stieber Twins",
        album="Fenster zum Hof",
        genre="Hip-Hop, Rap",
        year="1997",
        track=track,
        total_tracks="22",
        disc="1",
        total_discs="1",
    )


def test_exact_title_beats_wrong_local_track_number():
    songs = [
        Song(
            title="Fenster zum Hof",
            artist="Stieber Twins",
            album_artist="Stieber Twins",
            album="Fenster zum Hof",
            track="2",
            total_tracks="22",
            disc="1",
            total_discs="1",
            path="102.flac",
        ),
        Song(
            title=(
                "Fenster zum Hof "
                "(Super Mario von Hacht Remix)"
            ),
            artist="Stieber Twins",
            album_artist="Stieber Twins",
            album="Fenster zum Hof",
            track="2",
            total_tracks="22",
            disc="1",
            total_discs="1",
            path="109.flac",
        ),
    ]
    album = DirectAlbumResult(
        provider="apple_music",
        album="Fenster zum Hof",
        album_artist="Stieber Twins",
        tracks=(
            album_track(
                "Fenster zum Hof",
                "2",
            ),
            album_track(
                (
                    "Fenster zum Hof "
                    "(Super Mario von Hacht Remix)"
                ),
                "9",
            ),
        ),
    )

    matches = match_album_tracks(
        songs,
        album,
    )

    assert matches[0].track == "2"
    assert matches[1].track == "9"


def test_track_number_is_fallback_when_title_differs():
    songs = [
        Song(
            title="Lokaler anderer Titel",
            artist="Artist",
            album_artist="Artist",
            album="Album",
            track="3",
            disc="1",
            path="03.flac",
        )
    ]
    album = DirectAlbumResult(
        provider="apple_music",
        album="Album",
        album_artist="Artist",
        tracks=(
            album_track(
                "Quelltitel",
                "3",
            ),
        ),
    )

    matches = match_album_tracks(
        songs,
        album,
    )

    assert matches[0].track == "3"
