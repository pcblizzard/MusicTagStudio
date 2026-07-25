"""Lädt die mitgelieferten externen Werkzeuge nach ``tools/``.

MusicTagStudio nutzt FFmpeg/ffprobe (Audio-Analyse, ReplayGain, Spektrogramm)
und fpcalc (akustischer Fingerabdruck / AcoustID). Diese Binärdateien werden
NICHT im Git-Repository gehalten (sie sind groß und teils GPL), sondern hier
als Build-Artefakte in ``tools/`` bereitgestellt:

    tools/ffmpeg/ffmpeg.exe
    tools/ffmpeg/ffprobe.exe
    tools/fpcalc/fpcalc.exe

Die App sucht die Werkzeuge zuerst dort und fällt sonst auf den System-PATH
zurück. Ein Portable-/Setup-Build packt den ``tools/``-Ordner einfach mit,
sodass Endnutzer nichts installieren oder herunterladen müssen.

Aufruf (einmalig als Entwickler oder im Build):

    python scripts/fetch_tools.py            # lädt fehlende Werkzeuge
    python scripts/fetch_tools.py --force    # lädt alles neu
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

FFMPEG_WINDOWS_URL = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)
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


def fetch_ffmpeg(*, force: bool) -> bool:
    target = TOOLS_DIR / "ffmpeg"
    ffmpeg = target / "ffmpeg.exe"
    ffprobe = target / "ffprobe.exe"

    if ffmpeg.is_file() and ffprobe.is_file() and not force:
        print("FFmpeg bereits vorhanden – übersprungen.")
        return True

    print("FFmpeg/ffprobe:")
    try:
        data = _download(FFMPEG_WINDOWS_URL)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            ffmpeg_bytes = _extract_member(archive, "bin/ffmpeg.exe")
            ffprobe_bytes = _extract_member(archive, "bin/ffprobe.exe")
    except Exception as error:  # noqa: BLE001 - klare Meldung statt Traceback
        print(f"  FEHLER: {error}", file=sys.stderr)
        return False

    if not (ffmpeg_bytes and ffprobe_bytes):
        print("  FEHLER: ffmpeg.exe/ffprobe.exe nicht im Archiv gefunden.",
              file=sys.stderr)
        return False

    target.mkdir(parents=True, exist_ok=True)
    ffmpeg.write_bytes(ffmpeg_bytes)
    ffprobe.write_bytes(ffprobe_bytes)
    print(f"  -> {ffmpeg}")
    print(f"  -> {ffprobe}")
    return True


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
    parser.add_argument(
        "--only",
        choices=("ffmpeg", "fpcalc"),
        help="Nur ein bestimmtes Werkzeug laden.",
    )
    args = parser.parse_args()

    ok = True
    if args.only in (None, "ffmpeg"):
        ok = fetch_ffmpeg(force=args.force) and ok
    if args.only in (None, "fpcalc"):
        ok = fetch_fpcalc(force=args.force) and ok

    if ok:
        print("\nFertig. Werkzeuge liegen unter tools/.")
        return 0

    print("\nMindestens ein Werkzeug konnte nicht geladen werden.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
