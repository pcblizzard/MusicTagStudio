from musictagstudio.direct_album_lookup import (
    DirectAlbumResult,
    DirectAlbumTrack,
)
from musictagstudio.models.song import Song
from musictagstudio.providers.apple_music import (
    AppleAlbumCandidate,
)
from musictagstudio.services import proposal


def make_track(number: int, title: str):
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


def test_more_complete_store_tracklist_wins(monkeypatch):
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
            path="C:/Album/07. Clueso - Minimum.flac",
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
            path="C:/Album/11. Clueso - Jedes Jahr.flac",
        ),
    ]

    def search_album(*args, country, **kwargs):
        return [
            AppleAlbumCandidate(
                collection_id="album-id",
                album="Deja Vu 1/2",
                artist="Clueso",
                track_count=14,
                year="2026",
                country=country,
                confidence=100,
            )
        ]

    def lookup(album_id, *, country):
        if country == "DE":
            tracks = (
                make_track(11, "Jedes Jahr"),
            )
        else:
            tracks = (
                make_track(7, "Minimum"),
                make_track(11, "Jedes Jahr"),
            )

        return DirectAlbumResult(
            provider="apple_music",
            album="Deja Vu 1/2",
            album_artist="Clueso",
            tracks=tracks,
        )

    monkeypatch.setattr(
        proposal,
        "search_apple_album",
        search_album,
    )
    monkeypatch.setattr(
        proposal,
        "lookup_apple_album_by_id",
        lookup,
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
            for candidate in result.candidates
            if candidate.source == "apple_music"
        )
        for result in results
    ]

    assert apple_titles == [
        "Minimum",
        "Jedes Jahr",
    ]
