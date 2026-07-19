from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .library_sources import MusicSource

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"

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
    language: str = "automatic"
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

    music_sources: tuple[MusicSource, ...] = ()
    load_sources_on_startup: bool = True
    scan_sources_on_startup: bool = False

    discogs_token: str = ""


def load_settings(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
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
    library = data.get(
        "library",
        {},
    )
    raw_sources = data.get(
        "music_sources",
        [],
    )
    media_library = data.get(
        "media_library",
        {},
    )

    theme = str(
        appearance.get(
            "theme",
            "automatic",
        )
    )
    language = str(
        appearance.get(
            "language",
            "automatic",
        )
    )
    if language not in {
        "automatic", "de", "en", "es", "fr", "it", "pt_PT", "pt_BR",
    }:
        language = "automatic"

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

    music_sources: list[MusicSource] = []

    if isinstance(
        raw_sources,
        list,
    ):
        for item in raw_sources:
            if not isinstance(
                item,
                dict,
            ):
                continue

            source_id = str(
                item.get(
                    "id",
                    "",
                )
            ).strip()
            path_value = str(
                item.get(
                    "path",
                    "",
                )
            ).strip()

            if not source_id or not path_value:
                continue

            music_sources.append(
                MusicSource(
                    source_id=source_id,
                    name=str(
                        item.get(
                            "name",
                            "",
                        )
                    ).strip()
                    or Path(
                        path_value
                    ).name
                    or path_value,
                    path=path_value,
                    enabled=bool(
                        item.get(
                            "enabled",
                            True,
                        )
                    ),
                )
            )

    return AppSettings(
        theme=theme,
        language=language,
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
        music_sources=tuple(
            music_sources
        ),
        load_sources_on_startup=bool(
            library.get(
                "load_sources_on_startup",
                True,
            )
        ),
        scan_sources_on_startup=bool(
            library.get(
                "scan_sources_on_startup",
                False,
            )
        ),
        discogs_token=str(
            media_library.get(
                "discogs_token",
                "",
            )
        ).strip(),
    )


def save_settings(
    settings: AppSettings,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> None:
    lines = [
        "[appearance]",
        f'theme = "{settings.theme}"',
        f'language = "{settings.language}"',
        "",
        "[providers]",
        f'selected = "{settings.selected_provider}"',
        (
            "enrich_missing_fields = "
            f"{str(settings.enrich_missing_fields).lower()}"
        ),
        f'apple_country = "{settings.apple_country.upper()}"',
        "",
        "[behavior]",
        (
            "preview_before_writing = "
            f"{str(settings.preview_before_writing).lower()}"
        ),
        "",
        "[normalization]",
        f'feature_handling = "{settings.feature_handling}"',
        "",
        "[cover_sources]",
        f'selected = "{settings.selected_cover_source}"',
        (
            "fallback_enabled = "
            f"{str(settings.cover_fallback_enabled).lower()}"
        ),
        f"minimum_size = {settings.minimum_cover_size}",
        (
            "cache_max_age_days = "
            f"{settings.cover_cache_max_age_days}"
        ),
        "",
        "[cover_output]",
        'master_pattern = "{album_artist} - {album}.front.{ext}"',
        f"embedded_size = {settings.embedded_cover_size}",
        f"embedded_quality = {settings.embedded_cover_quality}",
        f"folder_size = {settings.folder_cover_size}",
        f"folder_quality = {settings.folder_cover_quality}",
        'folder_pattern = "{album_artist} - {album}_400px.jpg"',
        (
            "artist_folder_levels_up = "
            f"{settings.artist_folder_levels_up}"
        ),
        "",
        "[audio_analysis]",
        (
            "parallel_jobs = "
            f"{settings.audio_analysis_parallel_jobs}"
        ),
        "",
        "[media_library]",
        f'discogs_token = "{_toml_string(settings.discogs_token)}"',
        "",
        "[library]",
        (
            "load_sources_on_startup = "
            f"{str(settings.load_sources_on_startup).lower()}"
        ),
        (
            "scan_sources_on_startup = "
            f"{str(settings.scan_sources_on_startup).lower()}"
        ),
        "",
    ]

    for source in settings.music_sources:
        lines.extend(
            [
                "[[music_sources]]",
                f'id = "{_toml_string(source.source_id)}"',
                f'name = "{_toml_string(source.name)}"',
                f'path = "{_toml_string(source.path)}"',
                (
                    "enabled = "
                    f"{str(source.enabled).lower()}"
                ),
                "",
            ]
        )

    Path(config_path).write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _toml_string(
    value: str,
) -> str:
    return str(value).replace(
        "\\",
        "\\\\",
    ).replace(
        '"',
        '\\"',
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
