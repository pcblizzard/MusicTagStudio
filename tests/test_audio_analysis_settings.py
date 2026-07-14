from pathlib import Path

from musictagstudio.settings import (
    AppSettings,
    load_settings,
    save_settings,
)


def test_parallel_analysis_setting_roundtrip(
    tmp_path: Path,
):
    config = tmp_path / "config.toml"
    settings = AppSettings(
        audio_analysis_parallel_jobs=6
    )

    save_settings(
        settings,
        config,
    )
    loaded = load_settings(config)

    assert (
        loaded.audio_analysis_parallel_jobs
        == 6
    )


def test_invalid_parallel_setting_uses_automatic(
    tmp_path: Path,
):
    config = tmp_path / "config.toml"
    config.write_text(
        "[audio_analysis]\n"
        "parallel_jobs = 99\n",
        encoding="utf-8",
    )

    assert (
        load_settings(
            config
        ).audio_analysis_parallel_jobs
        == 0
    )
