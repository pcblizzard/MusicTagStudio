from musictagstudio.providers.apple_music import (
    _title_score,
)


def test_remastered_and_remaster_are_equivalent():
    assert _title_score(
        "Hier Kommt Alex (Remastered)",
        "Hier Kommt Alex - 2019 Remaster",
    ) >= 50


def test_remixed_and_remix_are_equivalent():
    assert _title_score(
        "Song (Remixed)",
        "Song - Remix",
    ) >= 50
