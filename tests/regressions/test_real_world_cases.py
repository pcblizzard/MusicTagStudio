from musictagstudio.services.proposal import (
    _apple_album_title_variants,
    _year_only,
)
from musictagstudio.providers.apple_music import (
    _title_score,
)


def test_clueso_album_title_keeps_slash_and_variant():
    variants = _apple_album_title_variants(
        "Deja Vu 1/2"
    )

    assert "Deja Vu 1/2" in variants
    assert "Deja Vu 1 2" in variants


def test_stieber_twins_remix_is_not_base_title():
    assert _title_score(
        "Fenster zum Hof (Super Mario von Hacht Remix)",
        "Fenster zum Hof",
    ) < _title_score(
        "Fenster zum Hof (Super Mario von Hacht Remix)",
        "Fenster zum Hof - Super Mario von Hacht Remix",
    )


def test_remaster_synonym_remains_compatible():
    assert _title_score(
        "Hier Kommt Alex (Remastered)",
        "Hier Kommt Alex - 2019 Remaster",
    ) >= 50


def test_full_release_date_is_reduced_to_year():
    assert _year_only(
        "2026-02-27"
    ) == "2026"
