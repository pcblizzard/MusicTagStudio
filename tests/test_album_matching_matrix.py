from musictagstudio.direct_album_lookup import (
    DirectAlbumResult,
    DirectAlbumTrack,
    build_album_matching_result,
)
from musictagstudio.models.song import Song


def track(
    number: int,
    title: str,
    duration_ms: int = 200000,
) -> DirectAlbumTrack:
    return DirectAlbumTrack(
        title=title,
        artist="Stieber Twins",
        album_artist="Stieber Twins",
        album="Fenster zum Hof",
        genre="Hip-Hop, Rap",
        year="1997",
        track=str(number),
        total_tracks="22",
        disc="1",
        total_discs="1",
        duration_ms=duration_ms,
    )


def test_filename_prefix_and_title_correct_wrong_tags():
    songs = [
        Song(
            title="Fenster zum Hof",
            artist="Stieber Twins",
            album_artist="Stieber Twins",
            album="Fenster zum Hof",
            track="2",
            disc="1",
            path=(
                "C:/Music/102. Stieber Twins"
                " - Fenster zum Hof.flac"
            ),
        ),
        Song(
            # Tags sind falsch und entsprechen Track 2.
            title="Fenster zum Hof",
            artist="Stieber Twins",
            album_artist="Stieber Twins",
            album="Fenster zum Hof",
            track="2",
            disc="1",
            path=(
                "C:/Music/109. Stieber Twins"
                " - Fenster zum Hof "
                "(Super Mario von Hacht Remix).flac"
            ),
        ),
    ]
    album = DirectAlbumResult(
        provider="apple_music",
        album="Fenster zum Hof",
        album_artist="Stieber Twins",
        tracks=(
            track(
                2,
                "Fenster zum Hof",
                201000,
            ),
            track(
                9,
                (
                    "Fenster zum Hof "
                    "(Super Mario von Hacht Remix)"
                ),
                245000,
            ),
        ),
    )

    result = build_album_matching_result(
        songs,
        album,
    )

    assert result.mapping[0].track == "2"
    assert result.mapping[1].track == "9"
    assert result.complete


def test_global_assignment_never_uses_track_twice():
    songs = [
        Song(
            title="Same",
            path="01. Artist - Same.flac",
        ),
        Song(
            title="Same",
            path="02. Artist - Same.flac",
        ),
    ]
    album = DirectAlbumResult(
        provider="apple_music",
        album="Album",
        album_artist="Artist",
        tracks=(
            track(1, "Same"),
            track(2, "Same"),
        ),
    )

    result = build_album_matching_result(
        songs,
        album,
    )
    assigned = [
        value.track
        for value in result.mapping.values()
    ]

    assert sorted(assigned) == ["1", "2"]


def test_incomplete_when_file_has_no_reasonable_match():
    songs = [
        Song(
            title="Completely unrelated",
            path="unknown.flac",
        )
    ]
    album = DirectAlbumResult(
        provider="apple_music",
        album="Album",
        album_artist="Artist",
        tracks=(
            track(1, "Known title"),
        ),
    )

    result = build_album_matching_result(
        songs,
        album,
    )

    assert not result.complete
    assert result.unmatched_local_indexes == (0,)
