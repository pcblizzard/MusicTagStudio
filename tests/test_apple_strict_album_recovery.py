from musictagstudio.models.metadata import (
    MetadataCandidate,
)
from musictagstudio.models.song import Song
from musictagstudio.providers.apple_music import (
    AppleAlbumCandidate,
)
from musictagstudio.services import proposal
from musictagstudio.direct_album_lookup import (
    DirectAlbumResult,
    DirectAlbumTrack,
)


def track(
    number: int,
    title: str,
) -> DirectAlbumTrack:
    return DirectAlbumTrack(
        title=title,
        artist="Clueso",
        album_artist="Clueso",
        album="Deja Vu 1/2",
        genre="Pop",
        year="2026",
        track=str(number),
        total_tracks="14",
        disc="1",
        total_discs="1",
    )


def song(
    number: int,
    title: str,
) -> Song:
    return Song(
        title=title,
        artist="Clueso",
        album_artist="Clueso",
        album="Deja Vu 1/2",
        year="2026",
        track=f"{number:02d}",
        total_tracks="14",
        disc="1",
        total_discs="1",
        path=(
            f"C:/Album/{number:02d}. "
            f"Clueso - {title}.flac"
        ),
    )


def test_missing_lookup_track_is_recovered_strictly(
    monkeypatch,
):
    songs = [
        song(7, "Minimum"),
        song(11, "Jedes Jahr"),
    ]

    monkeypatch.setattr(
        proposal,
        "search_apple_album",
        lambda *args, **kwargs: [
            AppleAlbumCandidate(
                collection_id="1859696286",
                album="Deja Vu 1/2",
                artist="Clueso",
                track_count=14,
                year="2026",
                country=kwargs["country"],
                confidence=100,
            )
        ],
    )

    # Simuliert eine unvollständige Lookup-Antwort:
    # Track 7 fehlt, Track 11 ist vorhanden.
    monkeypatch.setattr(
        proposal,
        "lookup_apple_album_by_id",
        lambda *args, **kwargs:
        DirectAlbumResult(
            provider="apple_music",
            album="Deja Vu 1/2",
            album_artist="Clueso",
            tracks=(
                track(
                    11,
                    "Jedes Jahr",
                ),
            ),
        ),
    )

    calls = []

    def strict_search(
        title,
        artist,
        album,
        **kwargs,
    ):
        calls.append(
            (
                title,
                kwargs[
                    "collection_id"
                ],
                kwargs[
                    "wanted_track"
                ],
                kwargs[
                    "countries"
                ],
            )
        )

        if (
            title == "Minimum"
            and kwargs[
                "collection_id"
            ] == "1859696286"
            and kwargs[
                "wanted_track"
            ] == "07"
        ):
            return [
                MetadataCandidate(
                    source="apple_music",
                    confidence=100,
                    title="Minimum",
                    artist="Clueso",
                    album_artist="Clueso",
                    album="Deja Vu 1/2",
                    year="2026",
                    track="7",
                    total_tracks="14",
                    disc="1",
                    total_discs="1",
                    external_id=(
                        "1859696298"
                    ),
                    release_id=(
                        "1859696286"
                    ),
                )
            ]

        return []

    monkeypatch.setattr(
        proposal,
        "search_song_in_album",
        strict_search,
    )
    monkeypatch.setattr(
        proposal,
        "search_mb_release",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        proposal,
        "search_mb",
        lambda *args, **kwargs: [],
    )

    results = proposal.build_batch_proposals(
        songs
    )
    apple_titles = [
        next(
            candidate.title
            for candidate
            in result.candidates
            if candidate.source
            == "apple_music"
        )
        for result in results
    ]

    assert apple_titles == [
        "Minimum",
        "Jedes Jahr",
    ]
    assert any(
        call[0] == "Minimum"
        and call[1]
        == "1859696286"
        and call[2] == "07"
        and "US" in call[3]
        for call in calls
    )


def test_generic_wrong_song_is_not_used_after_album_recognition(
    monkeypatch,
):
    songs = [
        song(7, "Minimum"),
    ]

    monkeypatch.setattr(
        proposal,
        "search_apple_album",
        lambda *args, **kwargs: [
            AppleAlbumCandidate(
                collection_id="1859696286",
                album="Deja Vu 1/2",
                artist="Clueso",
                track_count=14,
                year="2026",
                country=kwargs["country"],
                confidence=100,
            )
        ],
    )
    monkeypatch.setattr(
        proposal,
        "lookup_apple_album_by_id",
        lambda *args, **kwargs:
        DirectAlbumResult(
            provider="apple_music",
            album="Deja Vu 1/2",
            album_artist="Clueso",
            tracks=(
                track(
                    11,
                    "Jedes Jahr",
                ),
            ),
        ),
    )
    monkeypatch.setattr(
        proposal,
        "search_song_in_album",
        lambda *args, **kwargs: [],
    )

    def forbidden_generic_search(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Generic Apple fallback must not run."
        )

    monkeypatch.setattr(
        proposal,
        "search_apple",
        forbidden_generic_search,
    )
    monkeypatch.setattr(
        proposal,
        "search_mb_release",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        proposal,
        "search_mb",
        lambda *args, **kwargs: [],
    )

    results = proposal.build_batch_proposals(
        songs
    )

    assert not any(
        candidate.source
        == "apple_music"
        for candidate
        in results[0].candidates
    )
    assert any(
        "collectionId" in warning
        for warning
        in results[0].warnings
    )
