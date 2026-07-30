from musictagstudio.library_audit.checker import (
    audit_library,
)
from musictagstudio.models.song import Song


def make_song(
    *,
    title: str,
    track: str,
    disc: str,
    path: str,
) -> Song:
    return Song(
        title=title,
        artist="Artist",
        album_artist="Artist",
        album="Album",
        track=track,
        total_tracks="2",
        disc=disc,
        total_discs="2",
        path=path,
    )


def test_same_track_number_on_different_discs_is_valid():
    songs = [
        make_song(
            title="Disc 1 Track 1",
            track="1",
            disc="1",
            path="d1t1.flac",
        ),
        make_song(
            title="Disc 2 Track 1",
            track="1",
            disc="2",
            path="d2t1.flac",
        ),
    ]

    summary = audit_library(songs)

    assert not any(
        issue.category == "Tracknummer"
        and "kommt" in issue.message
        for issue in summary.issues
    )


def test_duplicate_track_number_on_same_disc_lists_files():
    songs = [
        make_song(
            title="Original",
            track="18",
            disc="1",
            path="106. Fahrenheit 72.flac",
        ),
        make_song(
            title="Instrumental",
            track="18",
            disc="1",
            path=(
                "118. Fahrenheit 72 "
                "[Instrumental].flac"
            ),
        ),
    ]

    summary = audit_library(songs)
    issue = next(
        issue
        for issue in summary.issues
        if (
            issue.category == "Tracknummer"
            and "Tracknummer 18" in issue.message
        )
    )

    assert "Disc 1" in issue.message
    assert "106. Fahrenheit 72.flac" in issue.details
    assert (
        "118. Fahrenheit 72 [Instrumental].flac"
        in issue.details
    )


def test_track_gaps_are_checked_per_disc():
    songs = [
        make_song(
            title="Disc 1 Track 1",
            track="1",
            disc="1",
            path="d1t1.flac",
        ),
        make_song(
            title="Disc 1 Track 3",
            track="3",
            disc="1",
            path="d1t3.flac",
        ),
        make_song(
            title="Disc 2 Track 1",
            track="1",
            disc="2",
            path="d2t1.flac",
        ),
    ]

    summary = audit_library(songs)

    messages = [
        issue.message
        for issue in summary.issues
        if issue.category == "Tracknummer"
    ]

    assert any(
        "Disc 1" in message
        and "2" in message
        for message in messages
    )
    assert not any(
        "Disc 2" in message
        and "fehl" in message
        for message in messages
    )
