from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .media_library.discogs import DiscogsProviderError, validate_token
from .providers.genius import GeniusProviderError, validate_access_token
from .providers.oauth_catalog import CatalogProviderError
from .providers.spotify import validate_credentials as validate_spotify
from .providers.tidal import validate_credentials as validate_tidal


@dataclass(frozen=True)
class ProviderDiagnostic:
    provider: str
    status: str
    message: str
    checked_at: str

    @property
    def successful(self) -> bool:
        return self.status == "available"


def check_provider_connections(
    *,
    discogs_token: str,
    tidal_client_id: str,
    tidal_client_secret: str,
    spotify_client_id: str,
    spotify_client_secret: str,
    genius_access_token: str,
) -> tuple[ProviderDiagnostic, ...]:
    checks: tuple[tuple[str, bool, Callable[[], None]], ...] = (
        (
            "Discogs",
            bool(discogs_token.strip()),
            lambda: validate_token(discogs_token),
        ),
        (
            "TIDAL",
            bool(tidal_client_id.strip()),
            lambda: validate_tidal(tidal_client_id, tidal_client_secret),
        ),
        (
            "Spotify",
            bool(spotify_client_id.strip() and spotify_client_secret.strip()),
            lambda: validate_spotify(
                spotify_client_id,
                spotify_client_secret,
            ),
        ),
        (
            "Genius",
            bool(genius_access_token.strip()),
            lambda: validate_access_token(genius_access_token),
        ),
    )
    checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
    return tuple(
        _run_check(provider, configured, check, checked_at)
        for provider, configured, check in checks
    )


def _run_check(
    provider: str,
    configured: bool,
    check: Callable[[], None],
    checked_at: str,
) -> ProviderDiagnostic:
    if not configured:
        return ProviderDiagnostic(
            provider,
            "not_configured",
            "Nicht eingerichtet",
            checked_at,
        )
    try:
        check()
    except (DiscogsProviderError, GeniusProviderError, CatalogProviderError) as error:
        return ProviderDiagnostic(
            provider,
            "error",
            _safe_error_message(error),
            checked_at,
        )
    except Exception:
        return ProviderDiagnostic(
            provider,
            "error",
            "Unerwarteter Fehler bei der Verbindungsprüfung",
            checked_at,
        )
    return ProviderDiagnostic(
        provider,
        "available",
        "Zugang gültig",
        checked_at,
    )


def _safe_error_message(error: Exception) -> str:
    message = " ".join(str(error).split())
    return message[:240] or "Verbindungsprüfung fehlgeschlagen"
