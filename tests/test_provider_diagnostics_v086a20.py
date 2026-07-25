from __future__ import annotations

from musictagstudio import provider_diagnostics
from musictagstudio.settings import AppSettings, load_settings, save_settings


def test_provider_diagnostics_separates_success_error_and_missing(monkeypatch):
    monkeypatch.setattr(provider_diagnostics, "validate_token", lambda _token: None)
    monkeypatch.setattr(
        provider_diagnostics,
        "validate_tidal",
        lambda *_args: (_ for _ in ()).throw(
            provider_diagnostics.CatalogProviderError("Berechtigung fehlt")
        ),
    )
    monkeypatch.setattr(
        provider_diagnostics,
        "validate_spotify",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        provider_diagnostics,
        "validate_access_token",
        lambda _token: None,
    )

    results = provider_diagnostics.check_provider_connections(
        discogs_token="discogs",
        tidal_client_id="tidal-id",
        tidal_client_secret="tidal-secret",
        spotify_client_id="",
        spotify_client_secret="",
        genius_access_token="genius",
    )
    statuses = {result.provider: result.status for result in results}

    assert statuses == {
        "Discogs": "available",
        "TIDAL": "error",
        "Spotify": "not_configured",
        "Genius": "available",
    }
    assert all("secret" not in result.message.casefold() for result in results)


def test_request_intervals_are_persisted_and_bounded(tmp_path):
    config = tmp_path / "config.toml"
    save_settings(
        AppSettings(
            apple_request_interval_seconds=2.5,
            genius_request_interval_seconds=0.5,
        ),
        config,
    )

    loaded = load_settings(config)

    assert loaded.apple_request_interval_seconds == 2.5
    assert loaded.genius_request_interval_seconds == 0.5


def test_apply_request_intervals_updates_shared_provider_clients(monkeypatch):
    from musictagstudio.providers import apple_http, genius
    from musictagstudio.settings import apply_request_intervals

    monkeypatch.setattr(apple_http, "REQUEST_INTERVAL_SECONDS", 1.5)
    monkeypatch.setattr(genius, "REQUEST_INTERVAL_SECONDS", 1.0)
    apply_request_intervals(
        AppSettings(
            apple_request_interval_seconds=2.0,
            genius_request_interval_seconds=0.5,
        )
    )

    assert apple_http.REQUEST_INTERVAL_SECONDS == 2.0
    assert genius.REQUEST_INTERVAL_SECONDS == 0.5
