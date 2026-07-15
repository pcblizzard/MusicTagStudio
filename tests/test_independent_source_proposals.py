from musictagstudio.models.metadata import (
    MetadataCandidate,
)
from musictagstudio.models.song import Song
from musictagstudio.services.proposal import (
    _proposal_result,
)


def test_sources_remain_independent():
    apple = MetadataCandidate(
        source="apple_music",
        confidence=100,
        title="Apple Title",
    )
    musicbrainz = MetadataCandidate(
        source="musicbrainz",
        confidence=95,
        title="MusicBrainz Title",
    )

    result = _proposal_result(
        Song(
            title="Local Title"
        ),
        [
            apple,
            musicbrainz,
        ],
        [],
        primary_source="apple_music",
        feature_handling="artist_only",
    )

    assert (
        result.candidate_for(
            "apple_music"
        ).title
        == "Apple Title"
    )
    assert (
        result.candidate_for(
            "musicbrainz"
        ).title
        == "MusicBrainz Title"
    )
    assert (
        result.sources[
            "apple_music"
        ].status
        == "matched"
    )
    assert (
        result.sources[
            "musicbrainz"
        ].status
        == "matched"
    )
