from __future__ import annotations

from musictagstudio.media_library.presentation import album_match_key, normalized


def test_edition_suffix_matches_plain_title():
    # Kern des Bugs: lokal "… (Premium Edition)", Katalog "Die …".
    assert album_match_key("Passion Whisky (Premium Edition)") == album_match_key(
        "Die Passion Whisky"
    )


def test_leading_article_ignored():
    assert album_match_key("The Wall") == album_match_key("Wall")
    assert album_match_key("Der Prozess") == album_match_key("Prozess")


def test_bracket_and_keyword_variants_align():
    base = album_match_key("Nevermind")
    assert album_match_key("Nevermind [Deluxe Edition]") == base
    assert album_match_key("Nevermind (Remastered)") == base
    assert album_match_key("Nevermind - Anniversary Version") == base


def test_distinct_albums_stay_distinct():
    assert album_match_key("Passion Whisky") != album_match_key("Passion Fruit")


def test_single_word_article_not_stripped_to_empty():
    # "Die" allein darf nicht zu leerem Schlüssel führen.
    assert album_match_key("Die") == normalized("die")


def test_key_is_stable_for_plain_titles():
    assert album_match_key("City of God") == normalized("city of god")
