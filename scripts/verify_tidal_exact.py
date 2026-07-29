"""Einmalige Verifikation der exakten TIDAL-Qualität mit deinem eigenen Konto.

Aufruf (aus dem Repository-Wurzelordner, mit Python 3.14):
    python scripts/verify_tidal_exact.py https://tidal.com/album/499754434
    # oder nur die ID:
    python scripts/verify_tidal_exact.py 499754434

Ablauf:
1. Es erscheint ein Login-Link + Code. Im Browser öffnen, mit deinem
   TIDAL-Konto (Hi-Fi/Plus) bestätigen.
2. Danach werden die TATSÄCHLICHE Bit-Tiefe/Abtastrate des Albums ausgegeben
   (das, was dein Konto streamen darf).

Wenn hier die echten Werte (z. B. 24 Bit / 48.0 kHz) erscheinen, wissen wir,
dass die App-Integration funktioniert – dann wird die UI verdrahtet.
"""

from __future__ import annotations

import re
import sys

from musictagstudio.providers import tidal_exact


def _album_id(argument: str) -> str:
    match = re.search(r"(\d{6,})", argument)
    return match.group(1) if match else argument.strip()


def main() -> int:
    if len(sys.argv) != 2:
        print("Aufruf: python scripts/verify_tidal_exact.py <TIDAL-Album-ID oder -URL>")
        return 2
    if not tidal_exact.is_available():
        print("tidalapi ist nicht installiert:  python -m pip install tidalapi")
        return 1

    album_id = _album_id(sys.argv[1])
    session = tidal_exact.new_session()
    login, future = tidal_exact.start_device_login(session)
    link = login.verification_uri_complete
    if not link.startswith("http"):
        link = "https://" + link
    print("Bitte im Browser öffnen und mit deinem TIDAL-Konto bestätigen:")
    print("   " + link)
    print("   (Code: " + str(login.user_code) + ")")
    print("Warte auf Autorisierung ...")
    future.result()  # blockiert, bis der Nutzer autorisiert hat

    if not session.check_login():
        print("Login nicht abgeschlossen.")
        return 1
    print("Eingeloggt. Ermittle exakte Qualität für Album", album_id, "...")
    quality = tidal_exact.album_exact_quality(session, album_id)
    print("")
    print("  Zusammenfassung:", quality.summary())
    print("  bit_depth   :", quality.bit_depth)
    print("  sample_rate :", quality.sample_rate)
    print("  audio_quality:", quality.audio_quality)
    if quality.error:
        print("  Hinweis     :", quality.error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
