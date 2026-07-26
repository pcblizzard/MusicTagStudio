"""Übersetzt die i18n-Kataloge (locales/*.json) mit DeepL und Google.

Dev-Werkzeug – die App ruft zur Laufzeit KEINE Übersetzungsdienste auf.
Die API-Schlüssel kommen ausschließlich aus Umgebungsvariablen und werden
niemals committet:

    DEEPL_API_KEY           (erforderlich)
    GOOGLE_TRANSLATE_API_KEY (optional; für den Zweitmeinungs-Abgleich)

Quelle ist standardmäßig Deutsch (locales/de.json). Übersetzt werden nur
fehlende Keys (mit --overwrite auch vorhandene).

Ablauf:
  1) python scripts/translate_i18n.py --languages en,es,fr,it,pt_PT,pt_BR
     -> Übereinstimmende DeepL/Google-Ergebnisse werden direkt geschrieben.
     -> Abweichungen landen in locales/_review_<lang>.json:
          "welcome": {"deepl": "…", "google": "…", "chosen": "deepl"}
  2) Review-Datei prüfen, ggf. "chosen" auf "google" ändern oder eigenen Wert
     als "custom" ergänzen.
  3) python scripts/translate_i18n.py --apply --languages es
     -> übernimmt die getroffene Auswahl in locales/es.json.

Weitere Optionen:
  --all-deepl        Alle in LANG_MAP hinterlegten Zielsprachen (aktuell ~30).
  --overwrite        Auch bereits vorhandene Keys neu übersetzen.
  --source de        Quellsprache (Standard de).
  --estimate         Nur Zeichen schätzen, nicht übersetzen.
  --google-cap N     Harte Google-Zeichengrenze/Monat (Standard 490000).
  --google-languages Nur diese Sprachen mit Google gegenprüfen.

Offline-Übersetzung (kein API-Budget) via Argos – benötigt `pip install ".[translate]"`:
  --provider argos   Alles offline mit Argos übersetzen (gratis, unbegrenzt).
  --fallback-argos   Bei erreichtem DeepL-Budget offline mit Argos weitermachen.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LOCALES_DIR = Path(__file__).resolve().parents[1] / "src" / "musictagstudio" / "locales"
USAGE_FILE = LOCALES_DIR / ".translation_usage.json"

# Harte Standard-Obergrenze für Google (Freikontingent 500.000/Monat).
DEFAULT_GOOGLE_CAP = 490_000

# Interne Sprachcodes -> (DeepL-Zielcode, Google-Zielcode).
LANG_MAP: dict[str, tuple[str, str]] = {
    "en": ("EN-US", "en"),
    "es": ("ES", "es"),
    "fr": ("FR", "fr"),
    "it": ("IT", "it"),
    "pt_PT": ("PT-PT", "pt-PT"),
    "pt_BR": ("PT-BR", "pt-BR"),
    "nl": ("NL", "nl"),
    "pl": ("PL", "pl"),
    "ru": ("RU", "ru"),
    "ja": ("JA", "ja"),
    "zh": ("ZH", "zh-CN"),
    "cs": ("CS", "cs"),
    "da": ("DA", "da"),
    "fi": ("FI", "fi"),
    "sv": ("SV", "sv"),
    "tr": ("TR", "tr"),
    "uk": ("UK", "uk"),
    "el": ("EL", "el"),
    "hu": ("HU", "hu"),
    "ro": ("RO", "ro"),
    "sk": ("SK", "sk"),
    "bg": ("BG", "bg"),
    "ko": ("KO", "ko"),
    "nb": ("NB", "no"),
    "id": ("ID", "id"),
    "et": ("ET", "et"),
    "lv": ("LV", "lv"),
    "lt": ("LT", "lt"),
    "sl": ("SL", "sl"),
    "ar": ("AR", "ar"),
}

# Schützt Platzhalter wie {count} vor der Übersetzung.
_PLACEHOLDER = re.compile(r"\{[^}]+\}")


def _protect(text: str) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = f"⟦{len(mapping)}⟧"  # ⟦0⟧, ⟦1⟧ – wird selten übersetzt
        mapping[token] = match.group(0)
        return token

    return _PLACEHOLDER.sub(replace, text), mapping


def _restore(text: str, mapping: dict[str, str]) -> tuple[str, bool]:
    intact = True
    for token, original in mapping.items():
        if token not in text:
            intact = False
        text = text.replace(token, original)
    return text, intact


def _deepl_endpoint(key: str) -> str:
    # Kostenlose DeepL-Schlüssel enden auf ":fx".
    host = "api-free.deepl.com" if key.strip().endswith(":fx") else "api.deepl.com"
    return f"https://{host}/v2/translate"


def _http_json(request: Request) -> dict:
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def deepl_translate(text: str, deepl_code: str, key: str, source: str) -> str:
    body = urlencode(
        {
            "text": text,
            "target_lang": deepl_code,
            "source_lang": source.upper(),
            "preserve_formatting": "1",
        }
    ).encode("utf-8")
    request = Request(
        _deepl_endpoint(key),
        data=body,
        headers={
            "Authorization": f"DeepL-Auth-Key {key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    payload = _http_json(request)
    return str(payload["translations"][0]["text"])


def google_translate(text: str, google_code: str, key: str, source: str) -> str:
    params = urlencode(
        {
            "q": text,
            "target": google_code,
            "source": source,
            "format": "text",
            "key": key,
        }
    )
    request = Request(
        f"https://translation.googleapis.com/language/translate/v2?{params}",
        method="POST",
    )
    payload = _http_json(request)
    return str(payload["data"]["translations"][0]["translatedText"])


# Interne Sprachcodes -> Argos-Code (ISO 639-1). pt_PT/pt_BR teilen sich "pt".
ARGOS_MAP: dict[str, str] = {
    "en": "en", "es": "es", "fr": "fr", "it": "it", "pt_PT": "pt", "pt_BR": "pt",
    "nl": "nl", "pl": "pl", "ru": "ru", "ja": "ja", "zh": "zh", "cs": "cs",
    "da": "da", "fi": "fi", "sv": "sv", "tr": "tr", "uk": "uk", "el": "el",
    "hu": "hu", "ro": "ro", "sk": "sk", "bg": "bg", "ko": "ko", "id": "id",
    "et": "et", "lv": "lv", "lt": "lt", "sl": "sl", "ar": "ar", "nb": "nb",
}

_argos_ready: set[tuple[str, str]] = set()


def _ensure_argos(from_code: str, to_code: str) -> None:
    """Stellt sicher, dass das Argos-Modell from->to (ggf. via Englisch) da ist."""
    if (from_code, to_code) in _argos_ready:
        return
    import argostranslate.package as pkg

    installed = {(p.from_code, p.to_code) for p in pkg.get_installed_packages()}

    def install(a: str, b: str) -> bool:
        if (a, b) in installed:
            return True
        pkg.update_package_index()
        match = next(
            (p for p in pkg.get_available_packages() if p.from_code == a and p.to_code == b),
            None,
        )
        if match is None:
            return False
        pkg.install_from_path(match.download())
        installed.add((a, b))
        return True

    if not install(from_code, to_code):
        # Kein Direktmodell -> über Englisch pivotieren (Argos übernimmt das).
        if not (install(from_code, "en") and install("en", to_code)):
            raise RuntimeError(f"Kein Argos-Modell {from_code}->{to_code} verfügbar.")
    _argos_ready.add((from_code, to_code))


def argos_translate(text: str, to_code: str, source: str) -> str:
    import argostranslate.translate as translate

    _ensure_argos(source, to_code)
    return str(translate.translate(text, source, to_code))


def deepl_usage(key: str) -> tuple[int, int]:
    """(verbraucht, Limit) an Zeichen laut DeepL – für die harte Budgetgrenze."""
    host = "api-free.deepl.com" if key.strip().endswith(":fx") else "api.deepl.com"
    request = Request(
        f"https://{host}/v2/usage",
        headers={"Authorization": f"DeepL-Auth-Key {key}"},
    )
    payload = _http_json(request)
    return int(payload.get("character_count", 0)), int(payload.get("character_limit", 0))


def _current_month() -> str:
    # Ohne Date.now()-Abhängigkeit: Monat aus DeepL-Nutzung ableiten wäre unnötig;
    # hier reicht die lokale Zeit für den Google-Monatszähler.
    return time.strftime("%Y-%m")


def _load_google_usage() -> int:
    if not USAGE_FILE.is_file():
        return 0
    try:
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return 0
    if data.get("google_month") != _current_month():
        return 0  # Monatswechsel -> Zähler zurückgesetzt
    return int(data.get("google_chars", 0))


def _save_google_usage(chars: int) -> None:
    USAGE_FILE.write_text(
        json.dumps({"google_month": _current_month(), "google_chars": chars}, indent=2),
        encoding="utf-8",
    )


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().casefold())


def load_catalog(lang: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{lang}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_catalog(lang: str, catalog: dict[str, str]) -> None:
    path = LOCALES_DIR / f"{lang}.json"
    ordered = {key: catalog[key] for key in sorted(catalog)}
    path.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _missing_items(source_catalog, lang, overwrite):
    catalog = load_catalog(lang)
    return [
        (key, text)
        for key, text in source_catalog.items()
        if overwrite or key not in catalog
    ]


def run_estimate(args, source_catalog) -> int:
    """Trockenlauf: zählt Quellzeichen, ohne zu übersetzen."""
    total = 0
    for lang in args.languages:
        if lang == args.source or lang not in LANG_MAP:
            continue
        chars = sum(len(text) for _key, text in _missing_items(source_catalog, lang, args.overwrite))
        google = chars if (not args.google_languages or lang in args.google_languages) else 0
        total += chars
        print(f"  {lang}: {chars} Zeichen (DeepL) · {google} Zeichen (Google)")
    google_total = sum(
        sum(len(t) for _k, t in _missing_items(source_catalog, lang, args.overwrite))
        for lang in args.languages
        if lang in LANG_MAP and lang != args.source
        and (not args.google_languages or lang in args.google_languages)
    )
    print(f"GESAMT: ~{total} Zeichen an DeepL, ~{google_total} an Google.")
    print("(Keine Übersetzung ausgeführt – nur Schätzung.)")
    return 0


def _require_argos() -> bool:
    try:
        import argostranslate.translate  # noqa: F401
        return True
    except ModuleNotFoundError:
        print(
            "Fehler: Paket 'argostranslate' fehlt. Installieren mit:\n"
            "  py -3.14 -m pip install \".[translate]\"",
            file=sys.stderr,
        )
        return False


def run_argos(args, source_catalog) -> int:
    """Übersetzt vollständig offline mit Argos – ohne API, Budget oder Google."""
    if not _require_argos():
        return 2
    print("Provider: Argos (offline, ohne Budget/Google).")
    for lang in args.languages:
        if lang == args.source or lang not in ARGOS_MAP:
            print(f"Überspringe {lang} (unbekannt oder = Quelle).")
            continue
        to_code = ARGOS_MAP[lang]
        catalog = load_catalog(lang)
        review: dict[str, dict[str, str]] = {}
        added = flagged = 0
        for key, source_text in _missing_items(source_catalog, lang, args.overwrite):
            protected, mapping = _protect(source_text)
            try:
                raw = argos_translate(protected, to_code, args.source)
            except Exception as error:  # noqa: BLE001 – Argos-Modellfehler nicht fatal
                print(f"  {lang}/{key}: Argos-Fehler ({error}).")
                continue
            out, ok = _restore(raw, mapping)
            catalog[key] = out
            added += 1
            if not ok:
                review[key] = {
                    "argos": out,
                    "chosen": "argos",
                    "placeholder_warnung": "Platzhalter evtl. verändert!",
                }
                flagged += 1
        save_catalog(lang, catalog)
        _finish_review(lang, review)
        print(f"{lang}: {added} via Argos übernommen ({flagged} mit Platzhalter-Warnung).")
    return 0


def run_translate(args) -> int:
    deepl_key = os.environ.get("DEEPL_API_KEY", "").strip()
    google_key = os.environ.get("GOOGLE_TRANSLATE_API_KEY", "").strip()

    source_catalog = load_catalog(args.source)
    if not source_catalog:
        print(f"Fehler: Quellkatalog locales/{args.source}.json ist leer.", file=sys.stderr)
        return 2

    if args.estimate:
        return run_estimate(args, source_catalog)

    if args.provider == "argos":
        return run_argos(args, source_catalog)

    if not deepl_key:
        print("Fehler: DEEPL_API_KEY ist nicht gesetzt.", file=sys.stderr)
        return 2

    # DeepL-Budget live prüfen und hart begrenzen.
    try:
        deepl_used, deepl_limit = deepl_usage(deepl_key)
        deepl_remaining = deepl_limit - deepl_used if deepl_limit else 10**9
        print(f"DeepL-Nutzung: {deepl_used}/{deepl_limit} Zeichen · verbleibend ~{deepl_remaining}.")
    except (HTTPError, URLError, KeyError, ValueError):
        deepl_remaining = 10**9
        print("DeepL-Nutzung nicht abrufbar – fahre ohne DeepL-Limitprüfung fort.")

    google_used = _load_google_usage()
    google_stopped = not google_key
    if google_key:
        print(f"Google-Verbrauch diesen Monat: {google_used}/{args.google_cap} (hart).")
    else:
        print("Hinweis: GOOGLE_TRANSLATE_API_KEY fehlt – ohne Zweitmeinung/Konflikte.")

    deepl_spent = 0
    fell_back = False  # nach DeepL-Budget-Stopp auf Argos umgeschaltet
    for lang in args.languages:
        if lang == args.source or lang not in LANG_MAP:
            print(f"Überspringe {lang} (unbekannt oder = Quelle).")
            continue
        deepl_code, google_code = LANG_MAP[lang]
        use_google_for_lang = bool(google_key) and (
            not args.google_languages or lang in args.google_languages
        )
        catalog = load_catalog(lang)
        review: dict[str, dict[str, str]] = {}
        added = conflicts = 0

        for key, source_text in _missing_items(source_catalog, lang, args.overwrite):
            # Harte DeepL-Grenze: nicht überschreiten.
            if not fell_back and deepl_spent + len(source_text) > deepl_remaining:
                if args.fallback_argos and _require_argos():
                    fell_back = True
                    print("  DeepL-Budget erreicht – ab hier Argos (offline).")
                else:
                    print(f"  DeepL-Budget erreicht – Abbruch bei {lang}/{key}.")
                    save_catalog(lang, catalog)
                    _finish_review(lang, review)
                    print(f"{lang}: {added} übernommen, {conflicts} Konflikte (DeepL-Budget-Stopp).")
                    return 0

            protected, mapping = _protect(source_text)
            try:
                if fell_back:
                    primary_raw = argos_translate(protected, ARGOS_MAP[lang], args.source)
                else:
                    primary_raw = deepl_translate(protected, deepl_code, deepl_key, args.source)
                    deepl_spent += len(source_text)
            except Exception as error:  # noqa: BLE001 – einzelner Fehler nicht fatal
                print(f"  {lang}/{key}: Übersetzungsfehler ({error}) – übersprungen.")
                continue
            deepl_out, deepl_ok = _restore(primary_raw, mapping)

            google_out = None
            if not fell_back and use_google_for_lang and not google_stopped:
                # Harte Google-Grenze: davor stoppen, NICHT überschreiten.
                if google_used + len(source_text) > args.google_cap:
                    google_stopped = True
                    print(f"  Google-Budget ({args.google_cap}) erreicht – ab hier nur DeepL.")
                else:
                    try:
                        google_raw = google_translate(protected, google_code, google_key, args.source)
                        google_out, _ = _restore(google_raw, mapping)
                        google_used += len(source_text)
                        _save_google_usage(google_used)
                    except (HTTPError, URLError, KeyError, ValueError) as error:
                        print(f"  {lang}/{key}: Google-Fehler ({error}).")

            time.sleep(0.1)

            if google_out is not None and _norm(deepl_out) != _norm(google_out):
                review[key] = {"deepl": deepl_out, "google": google_out, "chosen": "deepl"}
                conflicts += 1
            else:
                catalog[key] = deepl_out
                added += 1
            if not deepl_ok:
                review.setdefault(key, {"deepl": deepl_out, "chosen": "deepl"})
                review[key]["placeholder_warnung"] = "Platzhalter evtl. verändert!"

        save_catalog(lang, catalog)
        _finish_review(lang, review)
        print(
            f"{lang}: {added} direkt übernommen, {conflicts} Konflikte "
            f"({'locales/_review_' + lang + '.json' if review else 'keine'})."
        )

    print(f"Fertig. DeepL diesen Lauf: ~{deepl_spent} Zeichen · Google-Monat: {google_used}/{args.google_cap}.")
    return 0


def _finish_review(lang: str, review: dict[str, dict[str, str]]) -> None:
    if not review:
        return
    (LOCALES_DIR / f"_review_{lang}.json").write_text(
        json.dumps(dict(sorted(review.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_apply(args) -> int:
    for lang in args.languages:
        review_path = LOCALES_DIR / f"_review_{lang}.json"
        if not review_path.is_file():
            print(f"{lang}: keine Review-Datei, übersprungen.")
            continue
        review = json.loads(review_path.read_text(encoding="utf-8"))
        catalog = load_catalog(lang)
        applied = 0
        for key, entry in review.items():
            chosen = entry.get("chosen", "deepl")
            value = entry.get("custom") if chosen == "custom" else entry.get(chosen)
            if value:
                catalog[key] = value
                applied += 1
        save_catalog(lang, catalog)
        print(f"{lang}: {applied} Auswahlen übernommen.")
    return 0


def _parse_languages(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows-Konsole (cp1252) absichern
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="i18n-Kataloge via DeepL/Google übersetzen.")
    parser.add_argument("--source", default="de", help="Quellsprache (Standard de).")
    parser.add_argument(
        "--languages",
        type=_parse_languages,
        default=["en", "es", "fr", "it", "pt_PT", "pt_BR"],
        help="Kommagetrennte Zielsprachen.",
    )
    parser.add_argument("--all-deepl", action="store_true", help="Alle bekannten Zielsprachen.")
    parser.add_argument("--overwrite", action="store_true", help="Vorhandene Keys neu übersetzen.")
    parser.add_argument("--apply", action="store_true", help="Review-Auswahl übernehmen.")
    parser.add_argument("--estimate", action="store_true", help="Nur Zeichen schätzen, nicht übersetzen.")
    parser.add_argument(
        "--google-cap", type=int, default=DEFAULT_GOOGLE_CAP,
        help=f"Harte Google-Zeichengrenze/Monat (Standard {DEFAULT_GOOGLE_CAP}).",
    )
    parser.add_argument(
        "--google-languages", type=_parse_languages, default=None,
        help="Nur diese Sprachen mit Google gegenprüfen (Rest DeepL-only).",
    )
    parser.add_argument(
        "--provider", choices=("deepl", "argos"), default="deepl",
        help="Primärer Übersetzer: deepl (API) oder argos (offline, gratis).",
    )
    parser.add_argument(
        "--fallback-argos", action="store_true",
        help="Bei erreichtem DeepL-Budget offline mit Argos weitermachen statt zu stoppen.",
    )
    args = parser.parse_args()

    if args.all_deepl:
        args.languages = [code for code in LANG_MAP if code != args.source]

    return run_apply(args) if args.apply else run_translate(args)


if __name__ == "__main__":
    raise SystemExit(main())
