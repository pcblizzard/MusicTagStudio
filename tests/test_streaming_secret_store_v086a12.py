from musictagstudio import secret_store
from musictagstudio.settings import AppSettings, load_settings, save_settings


def test_streaming_client_ids_are_saved_but_secrets_are_not(tmp_path):
    path = tmp_path / "config.toml"
    save_settings(
        AppSettings(
            tidal_client_id="tidal-id",
            spotify_client_id="spotify-id",
        ),
        path,
    )

    content = path.read_text(encoding="utf-8")
    loaded = load_settings(path)

    assert loaded.tidal_client_id == "tidal-id"
    assert loaded.spotify_client_id == "spotify-id"
    assert "client_secret" not in content


def test_secret_store_uses_keyring(monkeypatch):
    values = {}
    monkeypatch.setattr(
        secret_store.keyring,
        "set_password",
        lambda _service, name, value: values.__setitem__(name, value),
    )
    monkeypatch.setattr(
        secret_store.keyring,
        "get_password",
        lambda _service, name: values.get(name),
    )

    secret_store.set_secret(secret_store.TIDAL_CLIENT_SECRET, "top-secret")

    assert secret_store.get_secret(secret_store.TIDAL_CLIENT_SECRET) == "top-secret"
