from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from musictagstudio.ui.media_library_widget import store_search_url


def test_bandcamp_search():
    url = store_search_url("bandcamp", "Silla Passion Whisky")
    assert url.startswith("https://bandcamp.com/search?")
    assert "Silla" in url and "Passion" in url


def test_qobuz_uses_locale_from_country():
    assert "/de-de/" in store_search_url("qobuz", "A B", "de")
    assert "/fr-fr/" in store_search_url("qobuz", "A B", "fr")
    # Unbekanntes Land -> us-en Fallback.
    assert "/us-en/" in store_search_url("qobuz", "A B", "xx")


def test_seven_digital_search():
    assert store_search_url("7digital", "A B").startswith(
        "https://www.7digital.com/search?"
    )


def test_itunes_uses_country_and_term():
    url = store_search_url("itunes", "A B", "de")
    assert url.startswith("https://music.apple.com/de/search?")
    assert "term=" in url


def test_ebay_uses_country_tld():
    assert store_search_url("ebay", "A B", "de").startswith(
        "https://www.ebay.de/sch/i.html?"
    )
    assert store_search_url("ebay", "A B", "gb").startswith(
        "https://www.ebay.co.uk/sch/i.html?"
    )
    # Unbekanntes Land -> .com.
    assert store_search_url("ebay", "A B", "xx").startswith(
        "https://www.ebay.com/sch/i.html?"
    )
    assert "_nkw=" in store_search_url("ebay", "A B", "de")


def test_kleinanzeigen_is_de_slug():
    url = store_search_url("kleinanzeigen", "Silla Schmutzige Euros", "us")
    assert url == "https://www.kleinanzeigen.de/s-silla-schmutzige-euros/k0"


def test_empty_terms_or_unknown_store_yield_empty():
    assert store_search_url("bandcamp", "   ") == ""
    assert store_search_url("unknown", "A B") == ""
    assert store_search_url("kleinanzeigen", "  ") == ""


def test_terms_are_whitespace_normalized():
    url = store_search_url("bandcamp", "  Silla   Album  ")
    assert "Silla" in url and "Album" in url
