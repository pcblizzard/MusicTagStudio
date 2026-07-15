from musictagstudio.direct_album_lookup import (
    DirectAlbumResult,
    DirectAlbumTrack,
)
from musictagstudio.models.song import Song
from musictagstudio.providers.musicbrainz import (
    MusicBrainzReleaseCandidate,
)
from musictagstudio.services import proposal


def test_musicbrainz_shorter_remix_title_remains_available(monkeypatch):
    song = Song(
        title=(
            "Fenster zum Hof "
            "(Super Mario von Hacht Remix)"
        ),
        artist="Stieber Twins",
        album_artist="Stieber Twins",
        album="Fenster zum Hof",
        year="1997",
        track="9",
        total_tracks="22",
        disc="1",
        total_discs="1",
        path=(
            "C:/Album/109. Stieber Twins - "
            "Fenster zum Hof "
            "(Super Mario von Hacht Remix).flac"
        ),
    )

    monkeypatch.setattr(
        proposal,
        "search_apple_album",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        proposal,
        "search_apple",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        proposal,
        "search_mb_release",
        lambda *args, **kwargs: [
            MusicBrainzReleaseCandidate(
                release_id="release-id",
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
                DirectAlbumTrack(
                    title="Fenster zum Hof (remix)",
                    artist="Stieber Twins",
                    album_artist="Stieber Twins",
                    album="Fenster zum Hof",
                    genre="",
                    year="1997",
                    track="9",
                    total_tracks="22",
                    disc="1",
                    total_discs="1",
                ),
            ),
        ),
    )

    result = proposal.build_batch_proposals(
        [song]
    )[0]
    candidate = next(
        item
        for item in result.candidates
        if item.source == "musicbrainz"
    )

    assert candidate.title == (
        "Fenster zum Hof (remix)"
    )
    assert candidate.track == "9"
