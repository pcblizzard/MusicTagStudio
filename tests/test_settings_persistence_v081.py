
from musictagstudio.library_sources import new_source
from musictagstudio.settings import AppSettings, load_settings, save_settings


def test_music_sources_roundtrip_to_explicit_config(tmp_path):
    config = tmp_path / "config.toml"
    source = new_source(str(tmp_path / "Music"))
    save_settings(
        AppSettings(
            music_sources=(source,),
            language="de",
        ),
        config,
    )
    loaded = load_settings(config)
    assert loaded.music_sources == (source,)
    assert loaded.language == "de"


def test_default_config_path_is_module_relative():
    from musictagstudio import settings
    assert settings.DEFAULT_CONFIG_PATH.name == "config.toml"
    assert settings.DEFAULT_CONFIG_PATH.parent.name != ""
