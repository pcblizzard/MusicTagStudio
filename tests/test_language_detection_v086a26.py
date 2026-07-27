from __future__ import annotations

import locale

import pytest

from musictagstudio import i18n

# Echte Funktionsreferenz zum Importzeitpunkt festhalten. Die autouse-Fixture
# in conftest.py ersetzt spaeter das Modul-Attribut i18n.system_language durch
# eine DE-Konstante; dieser lokale Name bleibt davon unberuehrt und zeigt
# weiterhin auf die tatsaechliche Erkennungslogik.
_real_system_language = i18n.system_language


def _force_locale(monkeypatch, value):
    monkeypatch.setattr(locale, "getlocale", lambda *a, **k: (value, "UTF-8"))
    monkeypatch.setattr(locale, "getdefaultlocale", lambda *a, **k: (value, "UTF-8"))


@pytest.mark.parametrize(
    ("system_locale", "expected"),
    [
        ("de_DE", "de"),
        ("en_US", "en"),
        ("es_ES", "es"),
        ("fr_FR", "fr"),
        ("it_IT", "it"),
        ("pt_BR", "pt_BR"),
        ("pt_PT", "pt_PT"),
        # Portugiesisch ohne Region -> europaeisches Portugiesisch.
        ("pt", "pt_PT"),
        # Unbekannte Systemsprache faellt sauber auf Englisch zurueck.
        ("ja_JP", "en"),
        ("zh_CN", "en"),
    ],
)
def test_system_language_maps_locale(monkeypatch, system_locale, expected):
    _force_locale(monkeypatch, system_locale)
    assert _real_system_language() == expected


def test_system_language_falls_back_when_locale_unknown(monkeypatch):
    monkeypatch.setattr(locale, "getlocale", lambda *a, **k: (None, None))
    monkeypatch.setattr(locale, "getdefaultlocale", lambda *a, **k: (None, None))
    assert _real_system_language() == "en"


def test_resolve_language_passes_through_explicit_choice():
    # Explizite Wahl ist unabhaengig vom System-Locale (und von der Fixture).
    assert i18n.resolve_language("de") == "de"
    assert i18n.resolve_language("pt_BR") == "pt_BR"
    # Unbekannter expliziter Code -> Englisch.
    assert i18n.resolve_language("xx") == "en"
