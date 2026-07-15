from musictagstudio.providers.musicbrainz import (
    _release_match_score,
)


def test_exact_release_with_correct_track_count_ranks_high():
    score = _release_match_score(
        wanted_album="Fenster zum Hof",
        wanted_artist="Stieber Twins",
        expected_track_count=22,
        wanted_year="1997",
        album="Fenster zum Hof",
        artist="Stieber Twins",
        track_count=22,
        year="1997",
        status="Official",
        search_score=100,
    )

    assert score == 100
