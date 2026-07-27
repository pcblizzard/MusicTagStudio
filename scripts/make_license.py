"""Anbieter-Werkzeug: signierte Lizenzschlüssel erzeugen.

Benötigt den PRIVATEN Signierschlüssel (licensing_private_key.pem), der NUR
beim Anbieter liegt und niemals ausgeliefert/committet wird. Der zugehörige
öffentliche Schlüssel steckt in ``musictagstudio.licensing.PUBLIC_KEY_B64``.

Beispiele:
  # Vollzugriff (alle Premium-Features) für einen Kunden
  python scripts/make_license.py --name "Max Mustermann" --features "*"

  # Nur einzelne Features, an eine Maschine gebunden
  python scripts/make_license.py --name "Firma X" --features rename \
      --machine 3f9a...   # Fingerprint kommt aus der App (Einstellungen)

Der ausgegebene Schlüssel wird in der App unter Einstellungen eingetragen.
"""

from __future__ import annotations

import argparse
import base64
import json
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

DEFAULT_KEY_PATH = Path(__file__).resolve().parents[1] / "licensing_private_key.pem"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def load_private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit(f"{path} enthält keinen Ed25519-Schlüssel.")
    return key


def make_license(
    private_key: Ed25519PrivateKey,
    *,
    name: str,
    features: list[str],
    machine: str = "",
) -> str:
    payload: dict[str, object] = {
        "v": 1,
        "id": uuid.uuid4().hex,
        "name": name,
        "features": features,
    }
    if machine:
        payload["machine"] = machine

    # Kanonisch serialisieren, damit Signatur und Prüfung identische Bytes sehen.
    payload_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    signature = private_key.sign(payload_bytes)
    return f"{_b64url(payload_bytes)}.{_b64url(signature)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Signierte Lizenzschlüssel erzeugen.")
    parser.add_argument("--name", required=True, help="Lizenznehmer (nur Info).")
    parser.add_argument(
        "--features",
        default="*",
        help='Komma-Liste freigeschalteter Features oder "*" (alle). Standard: "*".',
    )
    parser.add_argument(
        "--machine",
        default="",
        help="Optionaler Maschinen-Fingerprint (Ein-Geräte-Bindung).",
    )
    parser.add_argument(
        "--key",
        type=Path,
        default=DEFAULT_KEY_PATH,
        help=f"Privater Schlüssel (PEM). Standard: {DEFAULT_KEY_PATH}",
    )
    args = parser.parse_args()

    if not args.key.is_file():
        raise SystemExit(
            f"Privater Schlüssel nicht gefunden: {args.key}\n"
            "Er liegt nur beim Anbieter und wird nicht ausgeliefert."
        )

    features = (
        ["*"]
        if args.features.strip() == "*"
        else [item.strip() for item in args.features.split(",") if item.strip()]
    )
    token = make_license(
        load_private_key(args.key),
        name=args.name,
        features=features,
        machine=args.machine.strip(),
    )
    print(token)


if __name__ == "__main__":
    main()
