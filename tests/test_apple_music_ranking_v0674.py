from musictagstudio.providers.apple_music import (
    _match_score,
)


COMMON = {
    "wanted_title": "Fenster zum Hof (remix)",
    "alternate_title": (
        "Fenster zum Hof "
        "(Super Mario von Hacht Remix)"
    ),
    "wanted_artist": "Stieber Twins",
    "wanted_album": "Fenster zum Hof",
    "wanted_disc": "1",
    "wanted_duration_ms": 247000,
    "artist": "Stieber Twins",
    "album": "Fenster zum Hof",
    "disc": "1",
}


def test_remix_beats_plain_track_with_correct_local_track():
    remix = _match_score(
        **COMMON,
        wanted_track="9",
        title=(
            "Fenster zum Hof "
            "(Super Mario von Hacht Remix)"
        ),
        track="9",
        duration_ms=247000,
    )
    plain = _match_score(
        **COMMON,
        wanted_track="9",
        title="Fenster zum Hof",
        track="2",
        duration_ms=363000,
    )

    assert remix > plain


def test_remix_still_beats_plain_when_local_track_tag_is_wrong():
    remix = _match_score(
        **COMMON,
        wanted_track="2",
        title=(
            "Fenster zum Hof "
            "(Super Mario von Hacht Remix)"
        ),
        track="9",
        duration_ms=247000,
    )
    plain = _match_score(
        **COMMON,
        wanted_track="2",
        title="Fenster zum Hof",
        track="2",
        duration_ms=363000,
    )

    assert remix > plain
