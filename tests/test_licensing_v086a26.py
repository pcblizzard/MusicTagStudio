from __future__ import annotations

import base64
import json

import pytest

from musictagstudio import licensing
from musictagstudio.licensing import (
    License,
    is_feature_enabled,
    load_license,
    verify_license,
)

# Testschlüsselpaar zur Laufzeit erzeugen – unabhängig vom (gitignored)
# Anbieter-Schlüssel, damit CI ohne Geheimnis testen kann.
crypto = pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)


def _keypair():
    priv = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization

    pub_b64 = base64.b64encode(
        priv.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    ).decode()
    return priv, pub_b64


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _sign(priv, payload: dict) -> str:
    payload_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return f"{_b64url(payload_bytes)}.{_b64url(priv.sign(payload_bytes))}"


def test_valid_license_verifies_and_grants():
    priv, pub = _keypair()
    token = _sign(priv, {"name": "Kunde", "features": ["rename"]})
    lic = verify_license(token, public_key_b64=pub)
    assert lic is not None
    assert lic.licensee == "Kunde"
    assert lic.grants("rename") and not lic.grants("other")


def test_wildcard_grants_everything():
    priv, pub = _keypair()
    token = _sign(priv, {"name": "Pro", "features": ["*"]})
    lic = verify_license(token, public_key_b64=pub)
    assert lic is not None and lic.grants("rename") and lic.grants("anything")


def test_tampered_payload_is_rejected():
    priv, pub = _keypair()
    token = _sign(priv, {"name": "Kunde", "features": ["rename"]})
    payload_part, _, sig = token.partition(".")
    # Nutzlast verändern (andere Feature-Liste), alte Signatur behalten.
    forged_payload = _b64url(json.dumps({"features": ["*"]}).encode())
    assert verify_license(f"{forged_payload}.{sig}", public_key_b64=pub) is None


def test_wrong_public_key_is_rejected():
    priv, _ = _keypair()
    _, other_pub = _keypair()
    token = _sign(priv, {"name": "X", "features": ["rename"]})
    assert verify_license(token, public_key_b64=other_pub) is None


@pytest.mark.parametrize("bad", ["", "   ", "nodot", "a.b.c.d", "!!!.@@@"])
def test_malformed_tokens_return_none(bad):
    assert verify_license(bad) is None


def test_feature_gating_defaults():
    # Nicht-Premium-Feature ist immer frei, auch ohne Lizenz.
    assert is_feature_enabled("some_free_feature", None) is True
    # Premium-Feature ohne Lizenz gesperrt.
    assert is_feature_enabled("rename", None) is False


def test_machine_binding(monkeypatch):
    priv, pub = _keypair()
    monkeypatch.setattr(licensing, "machine_fingerprint", lambda: "THIS-MACHINE")

    matching = _sign(priv, {"name": "X", "features": ["*"], "machine": "THIS-MACHINE"})
    assert load_license(matching, public_key_b64=pub) is not None

    other = _sign(priv, {"name": "X", "features": ["*"], "machine": "OTHER-MACHINE"})
    assert load_license(other, public_key_b64=pub) is None


def test_is_feature_enabled_with_license_object():
    lic = License(licensee="X", features=frozenset({"rename"}))
    assert is_feature_enabled("rename", lic) is True
