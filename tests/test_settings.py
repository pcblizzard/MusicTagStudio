from pathlib import Path

from musictagstudio.settings import load_settings


def test_feature_handling_from_config(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[normalization]\n'
        'feature_handling = "title_and_artist"\n',
        encoding="utf-8",
    )

    settings = load_settings(config)

    assert settings.feature_handling == "title_and_artist"


def test_invalid_feature_handling_uses_default(tmp_path: Path):
    config = tmp_path / "config.toml"
    config.write_text(
        '[normalization]\n'
        'feature_handling = "invalid"\n',
        encoding="utf-8",
    )

    settings = load_settings(config)

    assert settings.feature_handling == "artist_only"
