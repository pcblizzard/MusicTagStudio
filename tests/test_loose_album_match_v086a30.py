from __future__ import annotations

from musictagstudio.providers.streaming_catalog import (
    album_confidence,
    loose_album_key,
)


def test_edition_and_article_align():
    assert loose_album_key("Passion Whisky (Premium Edition)") == loose_album_key(
        "Die Passion Whisky"
    )


def test_remaster_aligns_with_plain():
    assert loose_album_key("Nevermind (Remastered)") == loose_album_key("Nevermind")


def test_common_edition_keywords_align():
    base = loose_album_key("Nevermind")
    for variant in (
        "Nevermind (Deluxe Edition)",
        "Nevermind (Super Deluxe Edition)",
        "Nevermind (Special Edition)",
        "Nevermind (Limited Edition)",
        "Nevermind (Collector's Edition)",
        "Nevermind (Expanded)",
        "Nevermind (Reissue)",
        "Nevermind (Bonus Track Version)",
        "Nevermind - Remastered 2011",
        "Nevermind (2011 Remaster)",
        "Nevermind (Anniversary Edition)",
    ):
        assert loose_album_key(variant) == base, variant


def test_pure_year_title_keeps_digits():
    # Kein Editions-Wort -> Jahr bleibt Teil des Titels.
    assert loose_album_key("1999") == "1999"
    assert loose_album_key("1984") != loose_album_key("1999")


def test_live_variant_stays_distinct_from_studio():
    # Inhaltsbestimmender Zusatz -> NICHT gleich der Studio-Fassung.
    assert loose_album_key("Album (Live In Berlin)") != loose_album_key("Album")


def test_remix_and_acoustic_stay_distinct():
    base = loose_album_key("Song")
    assert loose_album_key("Song (Remix)") != base
    assert loose_album_key("Song (Acoustic)") != base


def test_distinct_albums_stay_distinct():
    assert loose_album_key("Passion Whisky") != loose_album_key("Passion Fruit")


def _conf(wanted: str, actual: str, *, exp: int | None, tracks: int) -> int:
    return album_confidence(
        wanted_album=wanted,
        wanted_artist="Silla",
        wanted_year="2012",
        expected_track_count=exp,
        album=actual,
        artist="Silla",
        year="2012",
        track_count=tracks,
    )


def test_premium_edition_now_passes_threshold():
    # Katalog "Die Passion Whisky" (18 Titel) vs. Streaming-Premium (40 Titel).
    score = _conf(
        "Die Passion Whisky", "Passion Whisky (Premium Edition)", exp=18, tracks=40
    )
    assert score >= 70
