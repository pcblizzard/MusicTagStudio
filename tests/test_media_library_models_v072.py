from musictagstudio.media_library.service import (
    Edition,
    ReleaseGroup,
    Track,
)


def test_release_group_and_edition_keep_key_details():
    group = ReleaseGroup(
        release_group_id="group",
        title="Album",
        first_release_date="2024-01-01",
        primary_type="Album",
        secondary_types=("Compilation",),
    )
    edition = Edition(
        release_id="release",
        title="Album Deluxe",
        date="2024-02-01",
        country="DE",
        format="2×CD",
        medium_count=2,
        track_count=27,
    )

    assert group.primary_type == "Album"
    assert group.secondary_types == ("Compilation",)
    assert edition.medium_count == 2
    assert edition.track_count == 27


def test_track_supports_multiple_discs():
    track = Track(
        disc_number=2,
        track_number=7,
        title="Bonus",
    )

    assert track.disc_number == 2
    assert track.track_number == 7
