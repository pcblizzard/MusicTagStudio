from __future__ import annotations

from base64 import urlsafe_b64encode
from dataclasses import dataclass
from hashlib import sha256
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request
import webbrowser

from ..secret_store import (
    TIDAL_ACCESS_EXPIRES_AT,
    TIDAL_ACCESS_TOKEN,
    TIDAL_GRANTED_SCOPE,
    TIDAL_REFRESH_TOKEN,
    get_secret,
    set_secret,
)
from .oauth_catalog import CatalogProviderError, request_json


AUTHORIZE_ENDPOINT = "https://login.tidal.com/authorize"
TOKEN_ENDPOINT = "https://auth.tidal.com/v1/oauth2/token"
REDIRECT_URI = "http://127.0.0.1:8765/tidal/callback"
SCOPE = "search.read"
_refresh_lock = threading.Lock()


@dataclass(frozen=True)
class TidalAuthorizationRequest:
    url: str
    state: str
    code_verifier: str


@dataclass(frozen=True)
class TidalTokenSet:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str


def create_authorization_request(client_id: str) -> TidalAuthorizationRequest:
    cleaned_client_id = client_id.strip()
    if not cleaned_client_id:
        raise CatalogProviderError("Die TIDAL Client ID fehlt.")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = (
        urlsafe_b64encode(sha256(verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    query = urlencode(
        {
            "response_type": "code",
            "client_id": cleaned_client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    return TidalAuthorizationRequest(
        url=f"{AUTHORIZE_ENDPOINT}?{query}",
        state=state,
        code_verifier=verifier,
    )


def authorize_in_browser(client_id: str, *, timeout: float = 180.0) -> TidalTokenSet:
    authorization = create_authorization_request(client_id)
    callback = _CallbackResult()
    handler = _callback_handler(callback, authorization.state)
    try:
        server = HTTPServer(("127.0.0.1", 8765), handler)
    except OSError as error:
        raise CatalogProviderError(
            "Der lokale TIDAL-Anmeldeport 8765 ist bereits belegt."
        ) from error
    deadline = time.monotonic() + timeout
    try:
        if not webbrowser.open(authorization.url):
            raise CatalogProviderError(
                "Der Browser konnte für die TIDAL-Anmeldung nicht geöffnet werden."
            )
        while not callback.code and not callback.error:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            server.timeout = min(1.0, remaining)
            server.handle_request()
    finally:
        server.server_close()
    if callback.error:
        raise CatalogProviderError(callback.error)
    if not callback.code:
        raise CatalogProviderError(
            "Die TIDAL-Anmeldung wurde nicht innerhalb von drei Minuten abgeschlossen."
        )
    tokens = exchange_authorization_code(
        client_id=client_id,
        code=callback.code,
        code_verifier=authorization.code_verifier,
    )
    store_user_tokens(tokens)
    return tokens


def exchange_authorization_code(
    *,
    client_id: str,
    code: str,
    code_verifier: str,
) -> TidalTokenSet:
    return _request_tokens(
        {
            "grant_type": "authorization_code",
            "client_id": client_id.strip(),
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        },
        phase="TIDAL-Anmeldung",
    )


def refresh_user_token(
    refresh_token: str,
    *,
    client_id: str,
) -> TidalTokenSet:
    return _request_tokens(
        {
            "grant_type": "refresh_token",
            "client_id": client_id.strip(),
            "refresh_token": refresh_token.strip(),
        },
        phase="TIDAL-Token-Aktualisierung",
        fallback_refresh_token=refresh_token,
    )


def get_user_access_token(client_id: str) -> str:
    with _refresh_lock:
        access_token = get_secret(TIDAL_ACCESS_TOKEN).strip()
        try:
            expires_at = float(get_secret(TIDAL_ACCESS_EXPIRES_AT) or "0")
        except ValueError:
            expires_at = 0.0
        if access_token and time.time() < expires_at - 60:
            return access_token
        refresh_token = get_secret(TIDAL_REFRESH_TOKEN).strip()
        if not refresh_token:
            return ""
        try:
            tokens = refresh_user_token(refresh_token, client_id=client_id)
        except CatalogProviderError as error:
            if _is_definitive_refresh_rejection(error):
                disconnect_tidal()
            raise
        store_user_tokens(tokens)
        return tokens.access_token


def tidal_is_connected() -> bool:
    return bool(
        get_secret(TIDAL_REFRESH_TOKEN).strip()
        or get_secret(TIDAL_ACCESS_TOKEN).strip()
    )


def disconnect_tidal() -> None:
    for name in (
        TIDAL_ACCESS_TOKEN,
        TIDAL_REFRESH_TOKEN,
        TIDAL_ACCESS_EXPIRES_AT,
        TIDAL_GRANTED_SCOPE,
    ):
        set_secret(name, "")


def store_user_tokens(tokens: TidalTokenSet) -> None:
    set_secret(TIDAL_ACCESS_TOKEN, tokens.access_token)
    if tokens.refresh_token:
        set_secret(TIDAL_REFRESH_TOKEN, tokens.refresh_token)
    set_secret(
        TIDAL_ACCESS_EXPIRES_AT,
        str(time.time() + max(60, tokens.expires_in)),
    )
    set_secret(TIDAL_GRANTED_SCOPE, tokens.scope)


def _request_tokens(
    fields: dict[str, str],
    *,
    phase: str,
    fallback_refresh_token: str = "",
) -> TidalTokenSet:
    request = Request(
        TOKEN_ENDPOINT,
        data=urlencode(fields).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        payload = request_json(request)
    except CatalogProviderError as error:
        raise CatalogProviderError(f"{phase} fehlgeschlagen: {error}") from error
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise CatalogProviderError(f"{phase}: TIDAL hat kein Zugriffstoken geliefert.")
    try:
        expires_in = int(payload.get("expires_in") or 3600)
    except (TypeError, ValueError):
        expires_in = 3600
    return TidalTokenSet(
        access_token=access_token,
        refresh_token=str(
            payload.get("refresh_token") or fallback_refresh_token
        ).strip(),
        expires_in=expires_in,
        scope=str(payload.get("scope") or SCOPE).strip(),
    )


def _is_definitive_refresh_rejection(error: CatalogProviderError) -> bool:
    message = str(error).casefold()
    return (
        "invalid_grant" in message
        or "invalid refresh" in message
        or "http 401" in message
    )


@dataclass
class _CallbackResult:
    code: str = ""
    error: str = ""


def _callback_handler(
    result: _CallbackResult,
    expected_state: str,
) -> type[BaseHTTPRequestHandler]:
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/tidal/callback":
                self._respond(404, "Unbekannte Rückrufadresse.")
                return
            values = parse_qs(parsed.query)
            state = str((values.get("state") or [""])[0])
            if not state or not secrets.compare_digest(state, expected_state):
                result.error = (
                    "Die TIDAL-Anmeldung wurde aus Sicherheitsgründen abgelehnt."
                )
                self._respond(400, result.error)
                return
            provider_error = str((values.get("error") or [""])[0])
            if provider_error:
                detail = str((values.get("error_description") or [""])[0])
                result.error = "TIDAL hat die Anmeldung abgebrochen"
                if detail:
                    result.error += f": {detail}"
                self._respond(400, result.error)
                return
            result.code = str((values.get("code") or [""])[0])
            if not result.code:
                result.error = "TIDAL hat keinen Anmeldecode geliefert."
                self._respond(400, result.error)
                return
            self._respond(
                200,
                "TIDAL wurde mit MusicTagStudio verbunden. "
                "Dieses Browserfenster kann geschlossen werden.",
            )

        def _respond(self, status: int, message: str) -> None:
            body = (
                "<!doctype html><meta charset='utf-8'>"
                "<title>MusicTagStudio – TIDAL</title>"
                "<style>body{font:18px system-ui;margin:4rem;max-width:46rem}"
                "h1{font-size:1.5rem}</style>"
                f"<h1>MusicTagStudio</h1><p>{escape(message)}</p>"
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return CallbackHandler
