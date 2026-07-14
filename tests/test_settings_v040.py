from pathlib import Path

from musictagstudio.settings import (
    AppSettings,
    load_settings,
    save_settings,
)


def test_settings_roundtrip(tmp_path: Path):
    config = tmp_path / "config.toml"
    expected = AppSettings(
        theme="dark",
        selected_provider="musicbrainz",
        enrich_missing_fields=False,
        apple_country="AT",
        preview_before_writing=True,
        feature_handling="title_and_artist",
    )

    save_settings(expected, config)

    assert load_settings(config) == expected


def test_unsupported_provider_falls_back_to_apple(
    tmp_path: Path,
):
    config = tmp_path / "config.toml"
    config.write_text(
        '[providers]\n'
        'selected = "qobuz"\n',
        encoding="utf-8",
    )

    assert (
        load_settings(config).selected_provider
        == "apple_music"
    )
