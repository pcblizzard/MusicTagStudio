from musictagstudio.models.song import Song
from musictagstudio.services.release_text import (
    _build_tracklist,
)


def test_multidisc_tracklist_has_cd_sections_and_apple_titles():
    songs = [
        Song(
            title="Stark wie ein Löwe",
            artist=(
                "Matthias Reim, Maschine, "
                "Toni Krahl, Christin Stark"
            ),
            album_artist="Matthias Reim",
            track="7",
            disc="2",
            total_discs="2",
            path="C:/Album/CD2/07.flac",
        ),
        Song(
            title="4 Uhr 30",
            artist="Matthias Reim",
            album_artist="Matthias Reim",
            track="1",
            disc="1",
            total_discs="2",
            path="C:/Album/CD1/01.flac",
        ),
    ]
    apple_titles = {
        (1, 1): "4 Uhr 30",
        (2, 7): (
            "Stark wie ein Löwe "
            "(feat. Maschine, Toni Krahl & Christin Stark)"
        ),
    }

    result = _build_tracklist(
        songs,
        apple_titles=apple_titles,
    )

    assert result == (
        "[b]CD1[/b]:\n"
        "01. 4 Uhr 30\n\n"
        "[b]CD2[/b]:\n"
        "07. Stark wie ein Löwe "
        "(feat. Maschine, Toni Krahl & Christin Stark)"
    )


def test_single_disc_tracklist_has_no_cd_heading():
    songs = [
        Song(
            title="Titel",
            track="1",
            disc="1",
            total_discs="1",
            path="C:/Album/01.flac",
        )
    ]

    assert _build_tracklist(songs) == "01. Titel"
