from musictagstudio.media_library.service import ReleaseGroup
from musictagstudio.ui.media_library_widget import _merge_release_groups


def group(title, year, *, source="musicbrainz", **values):
    return ReleaseGroup(
        release_group_id=f"{source}:{title}",
        title=title,
        first_release_date=year,
        source=source,
        **values,
    )


def test_discogs_enriches_matching_musicbrainz_release():
    merged = _merge_release_groups(
        [group("Maske", "2004-04-26")],
        [
            group(
                "Maske",
                "2004",
                source="discogs",
                labels=("Aggro Berlin",),
                formats=("CD",),
                discogs_release_id=123,
            )
        ],
    )

    assert len(merged) == 1
    assert merged[0].source == "musicbrainz"
    assert merged[0].labels == ("Aggro Berlin",)
    assert merged[0].formats == ("CD",)
    assert merged[0].discogs_release_id == 123
    assert merged[0].discogs_contributions == ("Editionen", "Labels", "Formate")


def test_discogs_only_release_is_kept_as_additional_entry():
    merged = _merge_release_groups(
        [group("Maske", "2004")],
        [group("Maske X", "2024", source="discogs")],
    )

    assert len(merged) == 2
    assert {item.source for item in merged} == {"musicbrainz", "discogs"}


def test_discogs_replaces_unknown_musicbrainz_artist():
    merged = _merge_release_groups(
        [group("Deja Vu 1/2", "2026", artist="Unbekannter Künstler")],
        [
            group(
                "Deja Vu 1/2",
                "2026",
                source="discogs",
                artist="Clueso",
                discogs_release_id=4147642,
            )
        ],
    )

    assert merged[0].artist == "Clueso"
    assert "Künstler" in merged[0].discogs_contributions
