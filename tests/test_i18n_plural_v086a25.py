from __future__ import annotations

from musictagstudio.i18n import (
    SUPPORTED_LANGUAGES,
    tr,
    tr_plural,
)


def test_translations_loaded_from_locale_files():
    # de/en werden aus locales/*.json geladen (Kernkatalog vollstaendig).
    assert tr("save", "de") == "Speichern"
    assert tr("save", "en") == "Save"
    codes = {code for code, _label in SUPPORTED_LANGUAGES}
    assert {"de", "en", "es", "fr", "it", "pt_PT", "pt_BR"} <= codes


def test_tr_plural_selects_singular_and_plural():
    assert tr_plural("changes", 1, "de") == "1 Änderung"
    assert tr_plural("changes", 3, "de") == "3 Änderungen"
    assert tr_plural("changes", 1, "en") == "1 change"
    assert tr_plural("changes", 5, "en") == "5 changes"


def test_tr_placeholder_formatting():
    # Platzhalter werden gefuellt (Basis fuer f-String-Migration).
    assert tr("artist_search", "en", query="Danger Dan") == (
        "Searching for artist “Danger Dan”…"
    )


def test_tr_falls_back_to_english_then_key():
    # Unbekannter Sprachcode -> Englisch-Fallback (resolve_language -> "en").
    assert tr("welcome", "xx_unbekannt") == tr("welcome", "en")
    # Voellig unbekannter Key -> Key selbst.
    assert tr("gibt_es_nicht_xyz", "de") == "gibt_es_nicht_xyz"
