from musictagstudio.settings import (
    AppSettings,
    load_settings,
    save_settings,
)


def test_discogs_token_roundtrip(
    tmp_path,
):
    path = tmp_path / "config.toml"
    save_settings(
        AppSettings(
            discogs_token="secret-token",
        ),
        path,
    )
    loaded = load_settings(
        path
    )

    assert (
        loaded.discogs_token
        == "secret-token"
    )
