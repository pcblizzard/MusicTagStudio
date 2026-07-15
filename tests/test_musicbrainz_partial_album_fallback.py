from musictagstudio.direct_album_lookup import (
    DirectAlbumResult,
    DirectAlbumTrack,
)
from musictagstudio.models.metadata import (
    MetadataCandidate,
)
from musictagstudio.models.song import Song
from musictagstudio.providers.musicbrainz import (
    MusicBrainzReleaseCandidate,
)
from musictagstudio.services import proposal


def mb_track(
    number: int,
    title: str,
) -> DirectAlbumTrack:
    return DirectAlbumTrack(
        title=title,
        artist="Stieber Twins",
        album_artist="Stieber Twins",
        album="Fenster zum Hof",
        genre="",
        year="1997",
        track=str(number),
        total_tracks="22",
        disc="1",
        total_discs="1",
    )


def song(
    number: int,
    title: str,
) -> Song:
    return Song(
        title=title,
        artist="Stieber Twins",
        album_artist="Stieber Twins",
        album="Fenster zum Hof",
        genre="",
        year="1997",
        track=str(number),
        total_tracks="22",
        disc="1",
        total_discs="1",
        path=(
            f"C:/Album/{number:03d}. "
            f"Stieber Twins - {title}.flac"
        ),
    )


def test_unmatched_release_tracks_receive_single_search(
    monkeypatch,
):
    songs = [
        song(1, "Intro"),
        song(2, "Fenster zum Hof"),
    ]

    monkeypatch.setattr(
        proposal,
        "search_apple_album",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        proposal,
        "search_mb_release",
        lambda *args, **kwargs: [
            MusicBrainzReleaseCandidate(
                release_id="release-1",
                album="Fenster zum Hof",
                artist="Stieber Twins",
                track_count=22,
                year="1997",
                status="Official",
                country="DE",
                confidence=100,
            )
        ],
    )
    monkeypatch.setattr(
        proposal,
        "lookup_musicbrainz_release_by_id",
        lambda *args, **kwargs:
        DirectAlbumResult(
            provider="musicbrainz",
            album="Fenster zum Hof",
            album_artist="Stieber Twins",
            tracks=(
                mb_track(
                    2,
                    "Fenster zum Hof",
                ),
            ),
        ),
    )

    def single_search(
        title,
        artist,
        album,
        limit=10,
    ):
        if title == "Intro":
            return [
                MetadataCandidate(
                    source="musicbrainz",
                    confidence=95,
                    title="Intro",
                    artist="Stieber Twins",
                    album_artist="Stieber Twins",
                    album="Fenster zum Hof",
                    year="1997",
                    track="1",
                    total_tracks="22",
                    disc="1",
                    total_discs="1",
                )
            ]

        return []

    monkeypatch.setattr(
        proposal,
        "search_mb",
        single_search,
    )

    results = proposal.build_batch_proposals(
        songs
    )

    mb_titles = [
        next(
            candidate.title
            for candidate
            in result.candidates
            if candidate.source
            == "musicbrainz"
        )
        for result in results
    ]

    assert mb_titles == [
        "Intro",
        "Fenster zum Hof",
    ]
