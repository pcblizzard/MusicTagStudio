from __future__ import annotations
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from .provider_catalog import PROVIDERS_BY_ID
from .cover_source_catalog import COVER_SOURCES_BY_ID
FeatureHandling=Literal["artist_only","title_and_artist","source"]
ThemeMode=Literal["automatic","light","dark"]
@dataclass(frozen=True)
class AppSettings:
    theme:ThemeMode="automatic"
    selected_provider:str="apple_music"
    enrich_missing_fields:bool=True
    apple_country:str="DE"
    preview_before_writing:bool=True
    feature_handling:FeatureHandling="artist_only"
    selected_cover_source:str="apple_music"
    cover_fallback_enabled:bool=True
    minimum_cover_size:int=1000
    embedded_cover_size:int=1000
    embedded_cover_quality:int=100
    folder_cover_size:int=400
    folder_cover_quality:int=80
    artist_folder_levels_up:int=2
    cover_cache_max_age_days:int=30

def load_settings(config_path:str|Path="config.toml")->AppSettings:
    path=Path(config_path)
    if not path.is_file(): return AppSettings()
    try:
        with path.open("rb") as f: data=tomllib.load(f)
    except (OSError,tomllib.TOMLDecodeError): return AppSettings()
    appearance=data.get("appearance",{}); providers=data.get("providers",{}); behavior=data.get("behavior",{}); normalization=data.get("normalization",{}); cover=data.get("cover_sources",{}); output=data.get("cover_output",{})
    theme=str(appearance.get("theme","automatic")); theme=theme if theme in {"automatic","light","dark"} else "automatic"
    selected=str(providers.get("selected","apple_music")); p=PROVIDERS_BY_ID.get(selected)
    if p is None or p.status!="supported": selected="apple_music"
    selected_cover=str(cover.get("selected","apple_music")); cp=COVER_SOURCES_BY_ID.get(selected_cover)
    if cp is None or cp.status!="supported": selected_cover="apple_music"
    feature=str(normalization.get("feature_handling","artist_only")); feature=feature if feature in {"artist_only","title_and_artist","source"} else "artist_only"
    return AppSettings(theme=theme,selected_provider=selected,enrich_missing_fields=bool(providers.get("enrich_missing_fields",True)),apple_country=str(providers.get("apple_country","DE")).upper(),preview_before_writing=bool(behavior.get("preview_before_writing",True)),feature_handling=feature,
        selected_cover_source=selected_cover,cover_fallback_enabled=bool(cover.get("fallback_enabled",True)),minimum_cover_size=int(cover.get("minimum_size",1000)),embedded_cover_size=int(output.get("embedded_size",1000)),embedded_cover_quality=int(output.get("embedded_quality",100)),folder_cover_size=int(output.get("folder_size",400)),folder_cover_quality=int(output.get("folder_quality",80)),artist_folder_levels_up=int(output.get("artist_folder_levels_up",2)),cover_cache_max_age_days=int(cover.get("cache_max_age_days",30)))

def save_settings(settings:AppSettings,config_path:str|Path="config.toml")->None:
    content=(
        "[appearance]\n" + f'theme = "{settings.theme}"\n\n' +
        "[providers]\n" + f'selected = "{settings.selected_provider}"\n' +
        f'enrich_missing_fields = {str(settings.enrich_missing_fields).lower()}\n' +
        f'apple_country = "{settings.apple_country.upper()}"\n\n' +
        "[behavior]\n" + f'preview_before_writing = {str(settings.preview_before_writing).lower()}\n\n' +
        "[normalization]\n" + f'feature_handling = "{settings.feature_handling}"\n\n' +
        "[cover_sources]\n" + f'selected = "{settings.selected_cover_source}"\n' +
        f'fallback_enabled = {str(settings.cover_fallback_enabled).lower()}\n' +
        f'minimum_size = {settings.minimum_cover_size}\n' +
        f'cache_max_age_days = {settings.cover_cache_max_age_days}\n\n' +
        "[cover_output]\n" + 'master_pattern = "{album_artist} - {album}.front.{ext}"\n' +
        f'embedded_size = {settings.embedded_cover_size}\n' +
        f'embedded_quality = {settings.embedded_cover_quality}\n' +
        f'folder_size = {settings.folder_cover_size}\n' +
        f'folder_quality = {settings.folder_cover_quality}\n' +
        'folder_pattern = "{album_artist} - {album}_400px.jpg"\n' +
        f'artist_folder_levels_up = {settings.artist_folder_levels_up}\n'
    )
    Path(config_path).write_text(content,encoding="utf-8")
