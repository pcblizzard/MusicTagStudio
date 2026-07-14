from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .cover_source_catalog import COVER_SOURCES_BY_ID
from .provider_catalog import PROVIDERS_BY_ID


FeatureHandling = Literal[
    "artist_only",
    "title_and_artist",
    "source",
]

ThemeMode = Literal[
    "automatic",
    "light",
    "dark",
]


@dataclass(frozen=True)
class AppSettings:
    theme: ThemeMode = "automatic"
    selected_provider: str = "apple_music"
    enrich_missing_fields: bool = True
    apple_country: str = "DE"
    preview_before_writing: bool = True
    feature_handling: FeatureHandling = "artist_only"

    selected_cover_source: str = "apple_music"
    cover_fallback_enabled: bool = True
    minimum_cover_size: int = 1000
    embedded_cover_size: int = 1000
    embedded_cover_quality: int = 100
    folder_cover_size: int = 400
    folder_cover_quality: int = 80
    artist_folder_levels_up: int = 2
    cover_cache_max_age_days: int = 30

    # 0 bedeutet automatische Auswahl anhand des Systems.
    audio_analysis_parallel_jobs: int = 0


def load_settings(
    config_path: str | Path = "config.toml",
) -> AppSettings:
    path = Path(config_path)

    if not path.is_file():
        return AppSettings()

    try:
        with path.open("rb") as config_file:
            data = tomllib.load(config_file)
    except (
        OSError,
        tomllib.TOMLDecodeError,
    ):
        return AppSettings()

    appearance = data.get(
        "appearance",
        {},
    )
    providers = data.get(
        "providers",
        {},
    )
    behavior = data.get(
        "behavior",
        {},
    )
    normalization = data.get(
        "normalization",
        {},
    )
    cover = data.get(
        "cover_sources",
        {},
    )
    output = data.get(
        "cover_output",
        {},
    )
    audio_analysis = data.get(
        "audio_analysis",
        {},
    )

    theme = str(
        appearance.get(
            "theme",
            "automatic",
        )
    )

    if theme not in {
        "automatic",
        "light",
        "dark",
    }:
        theme = "automatic"

    selected_provider = str(
        providers.get(
            "selected",
            "apple_music",
        )
    )
    provider = PROVIDERS_BY_ID.get(
        selected_provider
    )

    if (
        provider is None
        or provider.status != "supported"
    ):
        selected_provider = "apple_music"

    selected_cover = str(
        cover.get(
            "selected",
            "apple_music",
        )
    )
    cover_provider = (
        COVER_SOURCES_BY_ID.get(
            selected_cover
        )
    )

    if (
        cover_provider is None
        or cover_provider.status
        != "supported"
    ):
        selected_cover = "apple_music"

    feature_handling = str(
        normalization.get(
            "feature_handling",
            "artist_only",
        )
    )

    if feature_handling not in {
        "artist_only",
        "title_and_artist",
        "source",
    }:
        feature_handling = "artist_only"

    parallel_jobs = _safe_int(
        audio_analysis.get(
            "parallel_jobs",
            0,
        ),
        default=0,
    )

    if parallel_jobs not in {
        0,
        2,
        4,
        6,
        8,
    }:
        parallel_jobs = 0

    return AppSettings(
        theme=theme,
        selected_provider=selected_provider,
        enrich_missing_fields=bool(
            providers.get(
                "enrich_missing_fields",
                True,
            )
        ),
        apple_country=str(
            providers.get(
                "apple_country",
                "DE",
            )
        ).upper(),
        preview_before_writing=bool(
            behavior.get(
                "preview_before_writing",
                True,
            )
        ),
        feature_handling=feature_handling,
        selected_cover_source=selected_cover,
        cover_fallback_enabled=bool(
            cover.get(
                "fallback_enabled",
                True,
            )
        ),
        minimum_cover_size=_safe_int(
            cover.get(
                "minimum_size",
                1000,
            ),
            default=1000,
        ),
        embedded_cover_size=_safe_int(
            output.get(
                "embedded_size",
                1000,
            ),
            default=1000,
        ),
        embedded_cover_quality=_safe_int(
            output.get(
                "embedded_quality",
                100,
            ),
            default=100,
        ),
        folder_cover_size=_safe_int(
            output.get(
                "folder_size",
                400,
            ),
            default=400,
        ),
        folder_cover_quality=_safe_int(
            output.get(
                "folder_quality",
                80,
            ),
            default=80,
        ),
        artist_folder_levels_up=_safe_int(
            output.get(
                "artist_folder_levels_up",
                2,
            ),
            default=2,
        ),
        cover_cache_max_age_days=_safe_int(
            cover.get(
                "cache_max_age_days",
                30,
            ),
            default=30,
        ),
        audio_analysis_parallel_jobs=parallel_jobs,
    )


def save_settings(
    settings: AppSettings,
    config_path: str | Path = "config.toml",
) -> None:
    content = (
        "[appearance]\n"
        f'theme = "{settings.theme}"\n\n'
        "[providers]\n"
        f'selected = "{settings.selected_provider}"\n'
        "enrich_missing_fields = "
        f"{str(settings.enrich_missing_fields).lower()}\n"
        f'apple_country = "{settings.apple_country.upper()}"\n\n'
        "[behavior]\n"
        "preview_before_writing = "
        f"{str(settings.preview_before_writing).lower()}\n\n"
        "[normalization]\n"
        f'feature_handling = "{settings.feature_handling}"\n\n'
        "[cover_sources]\n"
        f'selected = "{settings.selected_cover_source}"\n'
        "fallback_enabled = "
        f"{str(settings.cover_fallback_enabled).lower()}\n"
        f"minimum_size = {settings.minimum_cover_size}\n"
        "cache_max_age_days = "
        f"{settings.cover_cache_max_age_days}\n\n"
        "[cover_output]\n"
        'master_pattern = "{album_artist} - {album}.front.{ext}"\n'
        f"embedded_size = {settings.embedded_cover_size}\n"
        f"embedded_quality = {settings.embedded_cover_quality}\n"
        f"folder_size = {settings.folder_cover_size}\n"
        f"folder_quality = {settings.folder_cover_quality}\n"
        'folder_pattern = "{album_artist} - {album}_400px.jpg"\n'
        "artist_folder_levels_up = "
        f"{settings.artist_folder_levels_up}\n\n"
        "[audio_analysis]\n"
        "parallel_jobs = "
        f"{settings.audio_analysis_parallel_jobs}\n"
    )

    Path(config_path).write_text(
        content,
        encoding="utf-8",
    )


def _safe_int(
    value: object,
    *,
    default: int,
) -> int:
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default
