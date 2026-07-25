from __future__ import annotations

from base64 import urlsafe_b64encode
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import time
from urllib.parse import parse_qs, urlparse

from musictagstudio.providers import tidal, tidal_auth
from musictagstudio.providers.oauth_catalog import CatalogProviderError


def test_authorization_request_uses_pkce_and_configured_redirect():
    authorization = tidal_auth.create_authorization_request("client-id")
    query = parse_qs(urlparse(authorization.url).query)

    expected_challenge = (
        urlsafe_b64encode(sha256(authorization.code_verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == [tidal_auth.REDIRECT_URI]
    assert query["scope"] == ["search.read"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [expected_challenge]
    assert query["state"] == [authorization.state]


def test_authorization_code_exchange_sends_required_fields(monkeypatch):
    captured = {}

    def fake_request_json(request):
        captured["body"] = parse_qs(request.data.decode("utf-8"))
        return {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 7200,
            "scope": "search.read",
        }

    monkeypatch.setattr(tidal_auth, "request_json", fake_request_json)
    tokens = tidal_auth.exchange_authorization_code(
        client_id="client-id",
        code="authorization-code",
        code_verifier="verifier",
    )

    assert captured["body"] == {
        "grant_type": ["authorization_code"],
        "client_id": ["client-id"],
        "code": ["authorization-code"],
        "redirect_uri": [tidal_auth.REDIRECT_URI],
        "code_verifier": ["verifier"],
    }
    assert tokens.access_token == "access"
    assert tokens.refresh_token == "refresh"


def test_refresh_token_exchange_sends_client_id(monkeypatch):
    captured = {}

    def fake_request_json(request):
        captured["body"] = parse_qs(request.data.decode("utf-8"))
        return {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "scope": "search.read",
        }

    monkeypatch.setattr(tidal_auth, "request_json", fake_request_json)
    tokens = tidal_auth.refresh_user_token(
        "stored-refresh",
        client_id="client-id",
    )

    assert captured["body"] == {
        "grant_type": ["refresh_token"],
        "client_id": ["client-id"],
        "refresh_token": ["stored-refresh"],
    }
    assert tokens.access_token == "new-access"


def test_tidal_catalog_prefers_connected_user_token(monkeypatch):
    monkeypatch.setattr(
        tidal, "get_user_access_token", lambda *a, **k: "user-token"
    )

    def client_credentials_must_not_run(*args, **kwargs):
        raise AssertionError("client credentials should not be requested")

    monkeypatch.setattr(tidal, "_access_token", client_credentials_must_not_run)
    requests = []

    def fake_request_json(request):
        requests.append(request)
        return {"data": {}, "included": []}

    monkeypatch.setattr(tidal, "request_json", fake_request_json)
    result = tidal.search_albums(
        "Deja Vu 1/2",
        "Clueso",
        client_id="client-id",
        client_secret="client-secret",
    )

    assert result == []
    assert requests[0].headers["Authorization"] == "Bearer user-token"
    assert requests[0].headers["Accept"] == "application/vnd.api+json"


def test_tidal_catalog_explains_404_after_successful_login(monkeypatch):
    monkeypatch.setattr(
        tidal, "get_user_access_token", lambda *a, **k: "user-token"
    )
    monkeypatch.setattr(
        tidal,
        "request_json",
        lambda request: (_ for _ in ()).throw(
            CatalogProviderError("Der Anbieter meldet HTTP 404.")
        ),
    )

    try:
        tidal.search_albums(
            "Deja Vu 1/2",
            "Clueso",
            client_id="client-id",
            client_secret="client-secret",
        )
    except CatalogProviderError as error:
        message = str(error)
    else:
        raise AssertionError("TIDAL 404 should be reported")

    assert "Anmeldung ist gültig" in message
    assert "Katalog-Endpunkt" in message
    assert "HTTP 404" in message


def test_tidal_refresh_is_shared_between_parallel_workers(monkeypatch):
    values = {
        tidal_auth.TIDAL_ACCESS_TOKEN: "",
        tidal_auth.TIDAL_ACCESS_EXPIRES_AT: "0",
        tidal_auth.TIDAL_REFRESH_TOKEN: "refresh",
    }
    refresh_calls = []
    stored = []
    monkeypatch.setattr(
        tidal_auth,
        "get_secret",
        lambda name: values.get(name, ""),
    )

    def fake_refresh(_refresh_token, *, client_id=""):
        refresh_calls.append(True)
        time.sleep(0.05)
        values[tidal_auth.TIDAL_ACCESS_TOKEN] = "new-access"
        values[tidal_auth.TIDAL_ACCESS_EXPIRES_AT] = str(time.time() + 3600)
        return tidal_auth.TidalTokenSet(
            "new-access",
            "refresh",
            3600,
            "search.read",
        )

    monkeypatch.setattr(tidal_auth, "refresh_user_token", fake_refresh)
    monkeypatch.setattr(tidal_auth, "store_user_tokens", stored.append)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _value: tidal_auth.get_user_access_token("client-id"),
                range(2),
            )
        )

    assert results == ["new-access", "new-access"]
    assert len(refresh_calls) == 1
    assert len(stored) == 1


def test_tidal_callback_ignores_unrelated_first_request(monkeypatch):
    captured = {}

    def fake_handler(callback, _state):
        captured["callback"] = callback
        return object

    class FakeServer:
        def __init__(self, *_args):
            self.calls = 0
            self.timeout = 0.0

        def handle_request(self):
            self.calls += 1
            if self.calls == 2:
                captured["callback"].code = "authorization-code"

        def server_close(self):
            return None

    monkeypatch.setattr(tidal_auth, "_callback_handler", fake_handler)
    monkeypatch.setattr(tidal_auth, "HTTPServer", FakeServer)
    monkeypatch.setattr(tidal_auth.webbrowser, "open", lambda _url: True)
    monkeypatch.setattr(
        tidal_auth,
        "exchange_authorization_code",
        lambda **_kwargs: tidal_auth.TidalTokenSet(
            "access",
            "refresh",
            3600,
            "search.read",
        ),
    )
    monkeypatch.setattr(tidal_auth, "store_user_tokens", lambda _tokens: None)

    tokens = tidal_auth.authorize_in_browser("client", timeout=1)

    assert tokens.access_token == "access"
