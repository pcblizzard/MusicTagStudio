from musictagstudio.providers.apple_music import (
    _album_match_score,
)


def test_exact_album_artist_and_track_count_rank_high():
    score = _album_match_score(
        wanted_album="Deja Vu 1/2",
        wanted_artist="Clueso",
        expected_track_count=14,
        wanted_year="2026",
        album="Deja Vu 1/2",
        artist="Clueso",
        track_count=14,
        year="2026",
    )

    assert score == 100


def test_wrong_track_count_lowers_album_score():
    correct = _album_match_score(
        wanted_album="Deja Vu 1/2",
        wanted_artist="Clueso",
        expected_track_count=14,
        wanted_year="2026",
        album="Deja Vu 1/2",
        artist="Clueso",
        track_count=14,
        year="2026",
    )
    wrong = _album_match_score(
        wanted_album="Deja Vu 1/2",
        wanted_artist="Clueso",
        expected_track_count=14,
        wanted_year="2026",
        album="Deja Vu 1/2",
        artist="Clueso",
        track_count=2,
        year="2026",
    )

    assert correct > wrong
