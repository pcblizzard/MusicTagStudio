"""Akustischer Fingerabdruck über Chromaprint (fpcalc) + AcoustID.

Ablauf: Audiodatei -> fpcalc berechnet Fingerabdruck + Dauer -> AcoustID-API
liefert passende MusicBrainz-Recording-IDs. Mit dieser ID kann der bestehende
MusicBrainz-Lookup die vollständigen Tags laden.

Voraussetzungen:
- ``fpcalc`` (Teil von Chromaprint). Die App bevorzugt eine mitgelieferte
  Binärdatei unter ``providers/vendor/``; sonst wird der System-PATH genutzt.
- Ein AcoustID-Application-Key. Standard ist ``ACOUSTID_APP_KEY`` (mit der App
  ausgeliefert); er lässt sich in den Einstellungen überschreiben.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .. import __version__
from ..diagnostics import get_diagnostic_logger


# Wird beim Registrieren einer "MusicTagStudio"-App auf acoustid.org gesetzt
# und mit der App ausgeliefert. Das ist ein Client-/Anwendungs-Key (identifiziert
# nur die App bei AcoustID) – bewusst nicht geheim, darf im Quellcode stehen
# (wie z. B. bei MusicBrainz Picard). Nutzer können in den Einstellungen einen
# eigenen Key hinterlegen, der Vorrang hat.
ACOUSTID_APP_KEY = "irmXywNJcD"

ACOUSTID_ENDPOINT = "https://api.acoustid.org/v2/lookup"
ACOUSTID_USER_AGENT = f"MusicTagStudio/{__version__}"
FPCALC_TIMEOUT_SECONDS = 120
LOOKUP_TIMEOUT_SECONDS = 20

# Mitgelieferte Werkzeuge liegen unter <resource_root>/tools/ (gitignoriert, per
# scripts/fetch_tools.py befüllt). resource_root() zeigt in Entwicklung auf das
# Repository und als gebündelte Exe ins PyInstaller-Bundle.
def _tools_dir() -> Path:
    from ..diagnostics import resource_root

    return resource_root() / "tools" / "fpcalc"


class FingerprintError(RuntimeError):
    """Der Fingerabdruck oder die AcoustID-Abfrage ist fehlgeschlagen."""


@dataclass(frozen=True)
class FingerprintResult:
    duration: int
    fingerprint: str


@dataclass(frozen=True)
class AcoustIdMatch:
    score: float
    recording_id: str
    title: str
    artist: str


def find_fpcalc(explicit_path: str = "") -> str | None:
    """Sucht die fpcalc-Binärdatei: expliziter Pfad, Bundle, dann PATH."""
    if explicit_path.strip():
        candidate = Path(explicit_path.strip())
        if candidate.is_file():
            return str(candidate)

    tools_dir = _tools_dir()
    for name in ("fpcalc.exe", "fpcalc"):
        bundled = tools_dir / name
        if bundled.is_file():
            return str(bundled)

    return shutil.which("fpcalc")


def find_fpcalc_dir() -> Path:
    """Zielverzeichnis für die mitgelieferte fpcalc-Binärdatei."""
    return _tools_dir()


def resolve_api_key(settings_key: str = "") -> str:
    """Bevorzugt den in den Einstellungen hinterlegten Key, sonst den App-Key."""
    return settings_key.strip() or ACOUSTID_APP_KEY.strip()


def compute_fingerprint(
    filepath: str | Path,
    *,
    fpcalc_path: str = "",
) -> FingerprintResult:
    """Berechnet Fingerabdruck und Dauer einer Datei über fpcalc."""
    logger = get_diagnostic_logger("fingerprint")
    executable = find_fpcalc(fpcalc_path)

    if executable is None:
        raise FingerprintError(
            "fpcalc (Chromaprint) wurde nicht gefunden. Bitte die Binärdatei "
            "mitliefern oder installieren."
        )

    command = [
        executable,
        "-json",
        "-length",
        "120",
        str(filepath),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=FPCALC_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.exception("fpcalc konnte nicht gestartet werden: %s", filepath)
        raise FingerprintError(
            f"fpcalc konnte nicht ausgeführt werden: {error}"
        ) from error

    if completed.returncode != 0:
        raise FingerprintError(
            "fpcalc meldete einen Fehler: "
            + (completed.stderr.strip() or "unbekannter Fehler")
        )

    try:
        payload = json.loads(completed.stdout)
        duration = int(round(float(payload["duration"])))
        fingerprint = str(payload["fingerprint"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise FingerprintError(
            "fpcalc lieferte eine unerwartete Antwort."
        ) from error

    if not fingerprint or duration <= 0:
        raise FingerprintError("fpcalc lieferte keinen gültigen Fingerabdruck.")

    return FingerprintResult(duration=duration, fingerprint=fingerprint)


def lookup(
    fingerprint: str,
    duration: int,
    *,
    api_key: str,
) -> list[AcoustIdMatch]:
    """Fragt die AcoustID-API ab und liefert MusicBrainz-Recording-Treffer."""
    if not api_key.strip():
        raise FingerprintError(
            "Es ist kein AcoustID-API-Key hinterlegt."
        )

    params = {
        "client": api_key.strip(),
        "duration": str(int(duration)),
        "fingerprint": fingerprint,
        "meta": "recordings",
        "format": "json",
    }
    request = Request(
        ACOUSTID_ENDPOINT,
        data=urlencode(params).encode("utf-8"),
        headers={
            "User-Agent": ACOUSTID_USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    try:
        with urlopen(request, timeout=LOOKUP_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except HTTPError as error:
        # AcoustID liefert auch bei Fehlern eine JSON-Meldung mit; die ist
        # deutlich hilfreicher als der nackte HTTP-Status (z. B. bei einem
        # ungültigen Key).
        message = _acoustid_error_message(error)
        raise FingerprintError(
            f"AcoustID meldet einen Fehler: {message}"
            if message
            else f"Die AcoustID-Abfrage ist fehlgeschlagen: HTTP {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise FingerprintError(
            f"Die AcoustID-Abfrage ist fehlgeschlagen: {error}"
        ) from error

    if payload.get("status") != "ok":
        message = str(
            (payload.get("error") or {}).get("message") or "unbekannter Fehler"
        )
        raise FingerprintError(f"AcoustID meldet einen Fehler: {message}")

    return _matches_from_payload(payload)


def identify_recording(
    filepath: str | Path,
    *,
    api_key: str,
    fpcalc_path: str = "",
) -> list[AcoustIdMatch]:
    """Vollständiger Weg von der Datei zu passenden Recording-Treffern."""
    result = compute_fingerprint(filepath, fpcalc_path=fpcalc_path)
    return lookup(
        result.fingerprint,
        result.duration,
        api_key=api_key,
    )


def _acoustid_error_message(error: HTTPError) -> str:
    try:
        body = json.loads(error.read().decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError, ValueError):
        return ""

    return str((body.get("error") or {}).get("message") or "")


def _matches_from_payload(payload: dict) -> list[AcoustIdMatch]:
    matches: list[AcoustIdMatch] = []

    for entry in payload.get("results", []) or []:
        score = float(entry.get("score") or 0.0)

        for recording in entry.get("recordings", []) or []:
            recording_id = str(recording.get("id") or "")

            if not recording_id:
                continue

            artists = recording.get("artists") or []
            artist = ", ".join(
                str(item.get("name") or "") for item in artists
            ).strip(", ")

            matches.append(
                AcoustIdMatch(
                    score=score,
                    recording_id=recording_id,
                    title=str(recording.get("title") or ""),
                    artist=artist,
                )
            )

    return sorted(matches, key=lambda match: -match.score)
