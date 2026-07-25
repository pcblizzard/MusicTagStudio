from __future__ import annotations

from typing import Final

import keyring
from keyring.errors import KeyringError, PasswordDeleteError


SERVICE_NAME: Final = "MusicTagStudio"
TIDAL_CLIENT_SECRET: Final = "tidal_client_secret"
TIDAL_ACCESS_TOKEN: Final = "tidal_access_token"
TIDAL_REFRESH_TOKEN: Final = "tidal_refresh_token"
TIDAL_ACCESS_EXPIRES_AT: Final = "tidal_access_expires_at"
TIDAL_GRANTED_SCOPE: Final = "tidal_granted_scope"
SPOTIFY_CLIENT_SECRET: Final = "spotify_client_secret"
GENIUS_ACCESS_TOKEN: Final = "genius_access_token"

_session_fallback: dict[str, str] = {}


def get_secret(name: str) -> str:
    try:
        value = keyring.get_password(SERVICE_NAME, name)
    except KeyringError:
        value = None
    return str(value or _session_fallback.get(name, ""))


def set_secret(name: str, value: str) -> None:
    cleaned = str(value or "").strip()
    if cleaned:
        _session_fallback[name] = cleaned
        try:
            keyring.set_password(SERVICE_NAME, name, cleaned)
        except KeyringError:
            pass
        return

    _session_fallback.pop(name, None)
    try:
        keyring.delete_password(SERVICE_NAME, name)
    except (KeyringError, PasswordDeleteError):
        pass
