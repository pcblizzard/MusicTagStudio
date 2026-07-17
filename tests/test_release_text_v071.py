from pathlib import Path

from musictagstudio.models.song import Song
from musictagstudio.services import release_text
from musictagstudio.settings import AppSettings


def test_release_text_template_and_path(
    monkeypatch,
    tmp_path,
):
    artist = tmp_path / "Artist"
    album = artist / "Album"
    album.mkdir(
        parents=True
    )
    songs = []

    for number, title in (
        (1, "First"),
        (2, "Second"),
    ):
        path = (
            album
            / f"{number:02d}.flac"
        )
        path.write_bytes(
            b"dummy"
        )
        songs.append(
            Song(
                title=title,
                artist="Artist",
                album_artist="Artist",
                album="Album",
                genre="Rock",
                year="2024",
                track=str(number),
                total_tracks="2",
                path=str(path),
            )
        )

    monkeypatch.setattr(
        release_text,
        "_load_apple_track_titles",
        lambda songs, settings: {},
    )
    monkeypatch.setattr(
        release_text,
        "find_ffmpeg",
        lambda configured_directory="":
        type(
            "Installation",
            (),
            {
                "available": False,
                "ffprobe_path": "",
            },
        )(),
    )
    settings = AppSettings(
        artist_folder_levels_up=1
    )
    result = (
        release_text.create_release_text(
            songs,
            settings,
        )
    )

    assert result.path == (
        artist
        / "Artist - Album.txt"
    )
    assert result.path.exists()
    assert (
        "[b]Artist - Album (2024)"
        in result.text
    )
    assert (
        "[b]Format[/b]: FLAC, RAR"
        in result.text
    )
    assert (
        "[spoiler]01. First\n02. Second[/spoiler]"
        in result.text
    )
    assert result.text.endswith(
        "Artist, Rock,"
    )


def test_sample_rate_uses_german_decimal_comma():
    assert (
        release_text._sample_rate_text(
            44100
        )
        == "44,1 kHz"
    )
