"""Online-Aktivierung über Keygen.sh (Seat-Limit, Ablauf, Widerruf).

Ergänzt die rein lokale Signaturprüfung aus :mod:`licensing` um eine
serverseitig durchgesetzte Lizenz: Der Client validiert den Lizenzschlüssel
gegen Keygen und bindet ihn beim ersten Mal an den Maschinen-Fingerprint
(node-locked). Ergebnis wird lokal mit **Kulanzfrist** gecacht, damit kurzes
Offline-Sein nicht sofort herabstuft.

Sicherheit: Es wird **kein** Admin-Token eingebettet. Authentifiziert wird nur
mit dem vom Kunden eingegebenen Lizenzschlüssel (``Authorization: License …``);
Account-ID und Public Key sind öffentlich.

Netzwerk und Cache-Logik sind getrennt (Transport injizierbar), damit die
Kernlogik ohne echtes Konto testbar bleibt.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# --- Konfiguration (aus dem Keygen-Dashboard; öffentlich, nicht geheim) ------
# Account-Slug/UUID aus den API-URLs (api.keygen.sh/v1/accounts/<HIER>/...).
KEYGEN_ACCOUNT_ID = "674d8ac1-8f62-479f-ac8f-d6e259bb7cda"
# Ed25519-Public-Key des Accounts als Hex (für optionale Offline-Signatur-
# prüfung signierter Schlüssel; im Online-Modell mit Scheme=None ungenutzt).
KEYGEN_PUBLIC_KEY_HEX = (
    "a618d4d566ffa78fa66ee14ebe44e45661898b9d8aeb371e869d759140e4f52b"
)

_API_BASE = "https://api.keygen.sh/v1/accounts"
_MEDIA_TYPE = "application/vnd.api+json"

# Fehlt die Aktivierung nur, weil die Maschine noch nicht registriert ist,
# lässt sich das durch eine Aktivierung heilen (dann erneut validieren).
_ACTIVATABLE_CODES = frozenset(
    {"NO_MACHINE", "NO_MACHINES", "FINGERPRINT_SCOPE_MISMATCH"}
)

# (method, url, headers, body) -> (status, parsed_json). Wirft bei Netzfehler.
Transport = Callable[[str, str, dict, bytes | None], "tuple[int, dict]"]


def is_configured() -> bool:
    return bool(KEYGEN_ACCOUNT_ID.strip())


@dataclass(frozen=True)
class KeygenResult:
    valid: bool
    code: str
    license_id: str = ""
    expiry: str = ""  # ISO-8601 oder leer (perpetual)
    detail: str = ""


def _urllib_transport(
    method: str, url: str, headers: dict, body: bytes | None
) -> tuple[int, dict]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        # Keygen liefert auch bei 4xx eine JSON-Antwort mit meta/code.
        try:
            return error.code, json.loads(error.read() or b"{}")
        except (ValueError, OSError):
            return error.code, {}


def _validate_key(
    transport: Transport, account_id: str, key: str, fingerprint: str
) -> KeygenResult:
    url = f"{_API_BASE}/{account_id}/licenses/actions/validate-key"
    body = json.dumps(
        {"meta": {"key": key, "scope": {"fingerprint": fingerprint}}}
    ).encode("utf-8")
    headers = {"Content-Type": _MEDIA_TYPE, "Accept": _MEDIA_TYPE}
    _status, payload = transport("POST", url, headers, body)

    meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
    data = payload.get("data") or {}
    attributes = data.get("attributes", {}) if isinstance(data, dict) else {}
    return KeygenResult(
        valid=bool(meta.get("valid", False)),
        code=str(meta.get("code", "")),
        license_id=str(data.get("id", "") if isinstance(data, dict) else ""),
        expiry=str(attributes.get("expiry") or ""),
        detail=str(meta.get("detail", "")),
    )


def _activate_machine(
    transport: Transport,
    account_id: str,
    key: str,
    license_id: str,
    fingerprint: str,
) -> None:
    url = f"{_API_BASE}/{account_id}/machines"
    body = json.dumps(
        {
            "data": {
                "type": "machines",
                "attributes": {"fingerprint": fingerprint},
                "relationships": {
                    "license": {"data": {"type": "licenses", "id": license_id}}
                },
            }
        }
    ).encode("utf-8")
    headers = {
        "Content-Type": _MEDIA_TYPE,
        "Accept": _MEDIA_TYPE,
        "Authorization": f"License {key}",
    }
    transport("POST", url, headers, body)


def check_license(
    key: str,
    fingerprint: str,
    *,
    account_id: str | None = None,
    transport: Transport | None = None,
) -> KeygenResult:
    """Validiert den Schlüssel online und aktiviert die Maschine bei Bedarf.

    Kann eine Netzwerk-Exception werfen (Aufrufer behandelt Offline-Fall über
    den Cache). Bei erreichbarem Server ist das Ergebnis autoritativ.
    """
    account_id = account_id if account_id is not None else KEYGEN_ACCOUNT_ID
    send = transport or _urllib_transport

    result = _validate_key(send, account_id, key, fingerprint)
    if result.valid:
        return result

    # Noch nicht an diese Maschine gebunden -> aktivieren und erneut prüfen.
    if result.code in _ACTIVATABLE_CODES and result.license_id:
        _activate_machine(send, account_id, key, result.license_id, fingerprint)
        return _validate_key(send, account_id, key, fingerprint)

    return result


# --- Cache mit Kulanzfrist (reine Logik, testbar) ----------------------------


@dataclass(frozen=True)
class CachedState:
    key_id: str  # Hash des Schlüssels, um Schlüsselwechsel zu erkennen
    last_valid: str  # ISO-Zeitpunkt der letzten erfolgreichen Prüfung
    expiry: str = ""  # ISO oder leer (perpetual)


def _hash_key(key: str) -> str:
    import hashlib

    return hashlib.sha256(key.strip().encode("utf-8")).hexdigest()[:16]


def evaluate_cache(
    cache: CachedState | None,
    key: str,
    now: datetime,
    *,
    grace_days: int = 14,
) -> bool:
    """Premium noch aktiv, wenn zuletzt gültig, innerhalb Kulanz und nicht abgelaufen.

    Wird nur herangezogen, wenn der Server nicht erreichbar ist.
    """
    if cache is None or cache.key_id != _hash_key(key):
        return False
    try:
        last_valid = datetime.fromisoformat(cache.last_valid)
    except ValueError:
        return False
    if _naive(now) > _naive(last_valid) + timedelta(days=grace_days):
        return False
    if cache.expiry:
        try:
            expiry = datetime.fromisoformat(cache.expiry.replace("Z", "+00:00"))
        except ValueError:
            expiry = None
        if expiry is not None and _naive(now) > _naive(expiry):
            return False
    return True


def _naive(value: datetime) -> datetime:
    """Vergleichbar machen: zeitzonenbehaftete Werte auf UTC-naiv reduzieren."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def make_cache_state(key: str, result: KeygenResult, now: datetime) -> CachedState:
    return CachedState(
        key_id=_hash_key(key),
        last_valid=now.isoformat(timespec="seconds"),
        expiry=result.expiry,
    )


# --- Persistenz + High-Level-Orchestrierung ---------------------------------


def default_cache_path() -> Path:
    from .diagnostics import project_root

    return Path(project_root()) / ".musictagstudio" / "license_cache.json"


def load_cache(path: Path) -> CachedState | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return CachedState(
        key_id=str(data.get("key_id", "")),
        last_valid=str(data.get("last_valid", "")),
        expiry=str(data.get("expiry", "")),
    )


def save_cache(path: Path, state: CachedState) -> None:
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "key_id": state.key_id,
                    "last_valid": state.last_valid,
                    "expiry": state.expiry,
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def cached_premium(license_key: str, *, now: datetime, cache_path: Path) -> bool:
    """Sofort-Einschätzung aus dem lokalen Cache (für den Programmstart)."""
    if not license_key.strip():
        return False
    return evaluate_cache(load_cache(cache_path), license_key, now)


def refresh_premium(
    license_key: str,
    fingerprint: str,
    *,
    now: datetime,
    cache_path: Path,
    transport: Transport | None = None,
    grace_days: int = 14,
) -> bool:
    """Prüft online und aktualisiert den Cache; nutzt bei Netzfehler die Kulanz.

    - Server erreichbar + gültig  -> Cache erneuern, True.
    - Server erreichbar + ungültig -> Cache verwerfen, False (autoritativ).
    - Server nicht erreichbar     -> Kulanzfrist aus dem Cache.
    Ist Keygen nicht konfiguriert oder kein Schlüssel gesetzt: False.
    """
    if not is_configured() or not license_key.strip():
        return False
    try:
        result = check_license(license_key, fingerprint, transport=transport)
    except OSError:
        return evaluate_cache(
            load_cache(cache_path), license_key, now, grace_days=grace_days
        )
    if result.valid:
        save_cache(cache_path, make_cache_state(license_key, result, now))
        return True
    # Autoritative Ablehnung (EXPIRED/SUSPENDED/…): Cache leeren.
    try:
        Path(cache_path).unlink()
    except OSError:
        pass
    return False
