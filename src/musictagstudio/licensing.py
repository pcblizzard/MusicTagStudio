"""Offline-Lizenzprüfung mit Ed25519-Signatur.

Feature-Gating ohne Server: Ein Lizenzschlüssel ist eine signierte Nutzlast
(Base64) ``payload.signature``. Die App trägt nur den **öffentlichen**
Schlüssel; signiert wird ausschließlich beim Anbieter mit dem privaten
Schlüssel (siehe ``scripts/make_license.py``). Ohne den privaten Schlüssel
lässt sich keine gültige Lizenz fälschen.

Bewusste Grenzen (ehrlich): Rein clientseitige Prüfung ist von einem
entschlossenen Angreifer mit lokalem Zugriff umgehbar (Binärpatch etc.).
Das schützt gegen Gelegenheits-Weitergabe, nicht gegen Cracking. Echte
Durchsetzung bräuchte Serverlogik. Maschinenbindung ist optional möglich,
im reinen Offline-Modell aber nur, wenn der Käufer seine Maschinen-ID vor
dem Signieren übermittelt.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Öffentlicher Signaturschlüssel dieser App-Auslieferung (Base64, Raw-Format).
# Das zugehörige private Gegenstück liegt NUR beim Anbieter
# (licensing_private_key.pem, gitignored).
PUBLIC_KEY_B64 = "J8z7r/5x4S3eSAQJt7FkTYz822rWl+gFbf5kCSII4xM="

# Zentrale Liste der Premium-Funktionen (Feature-Gating). Der Wildcard "*"
# in einer Lizenz schaltet alle frei. Neue Premium-Features hier ergänzen und
# an der Aufrufstelle mit require/is_feature_enabled prüfen.
PREMIUM_FEATURES: frozenset[str] = frozenset(
    {
        "rename",  # Datei-Umbenennung nach Schema
    }
)

WILDCARD = "*"


@dataclass(frozen=True)
class License:
    """Verifizierte Lizenz. ``features`` enthält freigeschaltete Funktionen."""

    licensee: str
    features: frozenset[str]
    license_id: str = ""
    machine: str = ""
    raw: dict[str, object] = field(default_factory=dict)

    def grants(self, feature: str) -> bool:
        return WILDCARD in self.features or feature in self.features


def _load_public_key(public_key_b64: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def verify_license(
    token: str,
    *,
    public_key_b64: str = PUBLIC_KEY_B64,
) -> License | None:
    """Prüft *token* und gibt bei gültiger Signatur die Lizenz zurück, sonst None.

    Deterministisch und offline: eine korrekt signierte Lizenz verifiziert
    immer – es gibt keine Netzwerk-/Zeitabhängigkeit, die zu einem
    versehentlichen Herabstufen führen könnte.
    """
    token = (token or "").strip()
    if not token or "." not in token:
        return None

    payload_part, _, signature_part = token.partition(".")
    try:
        payload_bytes = _b64url_decode(payload_part)
        signature = _b64url_decode(signature_part)
    except (binascii.Error, ValueError):
        return None

    try:
        _load_public_key(public_key_b64).verify(signature, payload_bytes)
    except (InvalidSignature, ValueError):
        return None

    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    features = data.get("features", [])
    if not isinstance(features, list):
        features = []

    return License(
        licensee=str(data.get("name", "")),
        features=frozenset(str(item) for item in features),
        license_id=str(data.get("id", "")),
        machine=str(data.get("machine", "")),
        raw=data,
    )


def load_license(
    token: str,
    *,
    public_key_b64: str = PUBLIC_KEY_B64,
) -> License | None:
    """Wie :func:`verify_license`, prüft zusätzlich eine Maschinenbindung.

    Ist in der Lizenz ein ``machine``-Wert gesetzt, muss er zum aktuellen
    Maschinen-Fingerprint passen; andernfalls gilt die Lizenz als ungültig.
    """
    license_ = verify_license(token, public_key_b64=public_key_b64)
    if license_ is None:
        return None
    if license_.machine and license_.machine != machine_fingerprint():
        return None
    return license_


def machine_fingerprint() -> str:
    """Stabile, maschinengebundene Kennung (best effort, Windows-tauglich).

    Kombiniert die Windows-MachineGuid mit dem Rechnernamen. Nicht als
    Sicherheitsmerkmal gedacht, sondern zur optionalen Ein-Geräte-Bindung.
    """
    import hashlib
    import platform

    parts: list[str] = [platform.node() or ""]
    try:  # Windows: MachineGuid aus der Registry
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
        ) as key:
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            parts.append(str(guid))
    except OSError:
        pass

    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:32]


def is_feature_enabled(feature: str, license_: License | None) -> bool:
    """True, wenn *feature* nutzbar ist.

    Nicht als Premium gelistete Funktionen sind immer frei; Premium-Funktionen
    nur mit einer Lizenz, die sie (oder ``*``) freischaltet.
    """
    if feature not in PREMIUM_FEATURES:
        return True
    return license_ is not None and license_.grants(feature)
