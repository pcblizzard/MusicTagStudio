"""Lädt die mitgelieferte fpcalc-Binärdatei nach ``tools/``.

MusicTagStudio nutzt fpcalc (akustischer Fingerabdruck / AcoustID). Die
Binärdatei wird NICHT im Git-Repository gehalten, sondern hier als
Build-Artefakt bereitgestellt:

    tools/fpcalc/fpcalc.exe

Die App sucht die Binärdatei zuerst dort und fällt sonst auf den System-PATH
zurück. Ein Portable-/Setup-Build packt den ``tools/``-Ordner mit, sodass
Endnutzer nichts installieren müssen.

FFmpeg wird NICHT mehr hier geladen: die Audio-Analyse (Loudness/ReplayGain/
Spektrogramm) läuft über PyAV (gebündeltes FFmpeg als pip-Abhängigkeit).

Aufruf (einmalig als Entwickler oder im Build):

    python scripts/fetch_tools.py            # lädt fpcalc, falls fehlend
    python scripts/fetch_tools.py --force    # lädt neu
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"

USER_AGENT = "MusicTagStudio-fetch-tools"

FPCALC_WINDOWS_URL = (
    "https://github.com/acoustid/chromaprint/releases/download/"
    "v1.6.0/chromaprint-fpcalc-1.6.0-windows-x86_64.zip"
)


def _download(url: str) -> bytes:
    print(f"  lade {url} …")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _extract_member(archive: zipfile.ZipFile, suffix: str) -> bytes | None:
    for name in archive.namelist():
        if name.replace("\\", "/").endswith(suffix):
            return archive.read(name)
    return None


def fetch_fpcalc(*, force: bool) -> bool:
    target = TOOLS_DIR / "fpcalc"
    fpcalc = target / "fpcalc.exe"

    if fpcalc.is_file() and not force:
        print("fpcalc bereits vorhanden – übersprungen.")
        return True

    print("fpcalc (Chromaprint):")
    try:
        data = _download(FPCALC_WINDOWS_URL)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            fpcalc_bytes = _extract_member(archive, "fpcalc.exe")
    except Exception as error:  # noqa: BLE001
        print(f"  FEHLER: {error}", file=sys.stderr)
        return False

    if not fpcalc_bytes:
        print("  FEHLER: fpcalc.exe nicht im Archiv gefunden.", file=sys.stderr)
        return False

    target.mkdir(parents=True, exist_ok=True)
    fpcalc.write_bytes(fpcalc_bytes)
    print(f"  -> {fpcalc}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bereits vorhandene Werkzeuge erneut herunterladen.",
    )
    args = parser.parse_args()

    if fetch_fpcalc(force=args.force):
        print("\nFertig. fpcalc liegt unter tools/fpcalc/.")
        return 0

    print("\nfpcalc konnte nicht geladen werden.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
