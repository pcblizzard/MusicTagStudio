from musictagstudio.media_library.presentation import (
    release_source_details,
    streaming_artist,
)
from musictagstudio.media_library.service import ReleaseGroup


def test_merged_release_lists_provider_contributions() -> None:
    group = ReleaseGroup(
        release_group_id="mb-1",
        title="Album",
        source="musicbrainz",
        labels=("Example Records",),
        formats=("CD",),
        cover_url="https://example.invalid/cover.jpg",
        discogs_release_id=42,
        discogs_contributions=("Labels", "Formate", "Cover"),
    )

    details = dict(release_source_details(group, "Lokal verfügbar"))

    assert details["MusicBrainz"] == "Stammdaten und Veröffentlichung"
    assert details["Discogs"] == "Labels, Formate, Cover"
    assert details["Apple Music"] == "Noch nicht geprüft"
    assert details["Lokale Bibliothek"] == "🟢 Lokal verfügbar"


def test_apple_music_result_is_reflected() -> None:
    group = ReleaseGroup(
        release_group_id="discogs:42",
        title="Album",
        source="discogs",
        discogs_release_id=42,
    )

    details = dict(
        release_source_details(
            group,
            "Nicht vorhanden",
            apple_music_status="found",
        )
    )

    assert "MusicBrainz" not in details
    assert details["Discogs"] == "Veröffentlichung und Editionen"
    assert details["Apple Music"] == "Verfügbarkeit bestätigt"
    assert details["Lokale Bibliothek"] == "⚪ Nicht vorhanden"


def test_unknown_group_artist_falls_back_to_selected_artist() -> None:
    assert streaming_artist("Unbekannter Künstler", "Clueso") == "Clueso"
    assert streaming_artist("Unknown Artist", "Clueso") == "Clueso"
    assert streaming_artist("Unbekannter Künstler", "Clueso") == "Clueso"


def test_known_group_artist_is_kept() -> None:
    assert streaming_artist("Clueso", "Anderer Treffer") == "Clueso"
