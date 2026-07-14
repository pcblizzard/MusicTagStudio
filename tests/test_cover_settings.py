from pathlib import Path
from musictagstudio.settings import AppSettings,save_settings,load_settings

def test_cover_settings_roundtrip(tmp_path:Path):
    path=tmp_path/'config.toml'; expected=AppSettings(selected_cover_source='cover_art_archive',cover_fallback_enabled=False,minimum_cover_size=1200,folder_cover_quality=80,artist_folder_levels_up=2)
    save_settings(expected,path); actual=load_settings(path)
    assert actual.selected_cover_source=='cover_art_archive'
    assert actual.cover_fallback_enabled is False
    assert actual.minimum_cover_size==1200
    assert actual.folder_cover_quality==80
