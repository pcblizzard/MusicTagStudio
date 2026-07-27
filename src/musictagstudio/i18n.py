from __future__ import annotations

import json
import locale
from pathlib import Path
from typing import Final


_LOCALES_DIR: Final[Path] = Path(__file__).resolve().parent / "locales"

# Anzeigenamen für die Sprachauswahl. Sprachen ohne Eintrag erscheinen mit ihrem
# Code – so lassen sich neue Sprachen allein durch eine neue locales/<code>.json
# ergänzen (z. B. für „alle DeepL-Sprachen").
LANGUAGE_LABELS: Final[dict[str, str]] = {
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "pt_PT": "Português (Portugal)",
    "pt_BR": "Português (Brasil)",
}

# Die Basissprache/Fallback ist Englisch.
FALLBACK_LANGUAGE: Final[str] = "en"


def _load_translations() -> dict[str, dict[str, str]]:
    catalogs: dict[str, dict[str, str]] = {}
    if not _LOCALES_DIR.is_dir():
        return catalogs
    for path in sorted(_LOCALES_DIR.glob("*.json")):
        # Interne Dateien (Review-Konflikte, Usage-Report) sind keine Sprachen.
        if path.name.startswith(("_", ".")):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if isinstance(data, dict):
            catalogs[path.stem] = {
                str(key): str(value) for key, value in data.items()
            }
    return catalogs


_TRANSLATIONS: Final[dict[str, dict[str, str]]] = _load_translations()


def _available_languages() -> tuple[tuple[str, str], ...]:
    codes = sorted(_TRANSLATIONS.keys())
    return tuple((code, LANGUAGE_LABELS.get(code, code)) for code in codes)


SUPPORTED_LANGUAGES: Final[tuple[tuple[str, str], ...]] = (
    ("automatic", "Automatisch (System)"),
    *_available_languages(),
)


def system_language() -> str:
    value = (
        locale.getlocale()[0] or locale.getdefaultlocale()[0] or FALLBACK_LANGUAGE
    ).replace("-", "_")
    lowered = value.lower()
    if lowered.startswith("pt_br") and "pt_BR" in _TRANSLATIONS:
        return "pt_BR"
    if lowered.startswith("pt") and "pt_PT" in _TRANSLATIONS:
        return "pt_PT"
    prefix = value.split("_", 1)[0].lower()
    return prefix if prefix in _TRANSLATIONS else FALLBACK_LANGUAGE


def resolve_language(value: str) -> str:
    if value == "automatic":
        return system_language()
    return value if value in _TRANSLATIONS else FALLBACK_LANGUAGE


def _lookup(key: str, resolved: str) -> str | None:
    text = _TRANSLATIONS.get(resolved, {}).get(key)
    if text is None and resolved != FALLBACK_LANGUAGE:
        text = _TRANSLATIONS.get(FALLBACK_LANGUAGE, {}).get(key)
    return text


def tr(key: str, language: str = "automatic", **values) -> str:
    """Übersetzt *key* in die gewählte Sprache (Fallback: Englisch, dann key).

    Platzhalter im Text (z. B. „{count} Titel geladen") werden mit **values
    gefüllt.
    """
    resolved = resolve_language(language)
    text = _lookup(key, resolved)
    if text is None:
        text = key
    return text.format(**values) if values else text


def _plural_category(count: int) -> str:
    """CLDR-nahe Pluralkategorie (aktuell 2-Form: one/other).

    Deckt Deutsch, Englisch, Spanisch, Französisch, Italienisch und
    Portugiesisch korrekt ab. Für Sprachen mit mehr Formen (z. B. Slawisch,
    Arabisch) ist dies eine bewusste Näherung.
    """
    return "one" if count == 1 else "other"


def tr_plural(key: str, count: int, language: str = "automatic", **values) -> str:
    """Wählt die Pluralform ``<key>_one`` / ``<key>_other`` anhand von *count*.

    ``count`` steht im Text zusätzlich als ``{count}`` zur Verfügung.
    Beispiel-Keys: ``changes_written_one`` / ``changes_written_other``.
    """
    resolved = resolve_language(language)
    category = _plural_category(count)
    text = _lookup(f"{key}_{category}", resolved)
    if text is None:
        # Fallback auf die jeweils andere Form bzw. den Basis-Key.
        other = "other" if category == "one" else "one"
        text = _lookup(f"{key}_{other}", resolved) or _lookup(key, resolved) or key
    return text.format(count=count, **values)
