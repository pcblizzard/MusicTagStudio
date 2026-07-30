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


def test_empty_terms_or_unknown_store_yield_empty():
    assert store_search_url("bandcamp", "   ") == ""
    assert store_search_url("unknown", "A B") == ""


def test_terms_are_whitespace_normalized():
    url = store_search_url("bandcamp", "  Silla   Album  ")
    assert "Silla" in url and "Album" in url
