from musictagstudio.direct_album_lookup import (
    DirectAlbumResult,
    DirectAlbumTrack,
)
from musictagstudio.models.song import Song
from musictagstudio.providers.apple_music import (
    AppleAlbumCandidate,
)
from musictagstudio.services import proposal


def make_track(
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


def test_batch_uses_full_album_tracklist(
    monkeypatch,
):
    songs = [
        Song(
            title="Minimum",
            artist="Clueso",
            album_artist="Clueso",
            album="Deja Vu 1/2",
            year="2026",
            track="07",
            total_tracks="14",
            disc="1",
            total_discs="1",
            path=(
                "C:/Music/Clueso/Deja Vu 1-2/"
                "07. Clueso - Minimum.flac"
            ),
        ),
        Song(
            title="Jedes Jahr",
            artist="Clueso, Chapo102",
            album_artist="Clueso",
            album="Deja Vu 1/2",
            year="2026",
            track="11",
            total_tracks="14",
            disc="1",
            total_discs="1",
            path=(
                "C:/Music/Clueso/Deja Vu 1-2/"
                "11. Clueso, Chapo102 - Jedes Jahr.flac"
            ),
        ),
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
                country="US",
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
            tracks=tuple(
                make_track(
                    number,
                    (
                        "Minimum"
                        if number == 7
                        else (
                            "Jedes Jahr"
                            if number == 11
                            else f"Track {number}"
                        )
                    ),
                )
                for number in range(
                    1,
                    15,
                )
            ),
        ),
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

    apple_0 = next(
        candidate
        for candidate
        in results[0].candidates
        if candidate.source
        == "apple_music"
    )
    apple_1 = next(
        candidate
        for candidate
        in results[1].candidates
        if candidate.source
        == "apple_music"
    )

    assert apple_0.title == "Minimum"
    assert apple_0.track == "7"
    assert apple_1.title == "Jedes Jahr"
    assert apple_1.track == "11"
