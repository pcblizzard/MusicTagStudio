from musictagstudio.library_audit.checker import (
    audit_library,
)
from musictagstudio.models.song import Song


def test_duplicate_isrc_and_album_values():
    songs = [
        Song(
            title="A",
            artist="Artist",
            album_artist="Artist",
            album="Album",
            genre="Hip-Hop, Rap",
            year="2020",
            track="1",
            total_tracks="2",
            disc="1",
            total_discs="1",
            isrc="DEAAA0000001",
            path="a.flac",
        ),
        Song(
            title="B",
            artist="Artist",
            album_artist="Different",
            album="Album",
            genre="Rap",
            year="2020",
            track="2",
            total_tracks="2",
            disc="1",
            total_discs="1",
            isrc="DEAAA0000001",
            path="b.flac",
        ),
    ]

    summary = audit_library(songs)
    categories = {
        issue.category
        for issue in summary.issues
    }

    assert "Doppelte ISRC" in categories
    assert (
        "Uneinheitliche Albumwerte"
        in categories
    )


def test_track_number_gap():
    songs = [
        Song(
            title="A",
            album_artist="Artist",
            album="Album",
            track="1",
            total_tracks="3",
            disc="1",
            total_discs="1",
            path="a.flac",
        ),
        Song(
            title="C",
            album_artist="Artist",
            album="Album",
            track="3",
            total_tracks="3",
            disc="1",
            total_discs="1",
            path="c.flac",
        ),
    ]

    summary = audit_library(songs)

    assert any(
        issue.category == "Tracknummer"
        and "Lücken" in issue.message
        for issue in summary.issues
    )
