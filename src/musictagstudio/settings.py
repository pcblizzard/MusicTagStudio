from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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


def load_settings(
    config_path: str | Path = "config.toml",
) -> AppSettings:
    path = Path(config_path)

    if not path.is_file():
        return AppSettings()

    try:
        with path.open("rb") as config_file:
            data = tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError):
        return AppSettings()

    appearance = data.get("appearance", {})
    providers = data.get("providers", {})
    behavior = data.get("behavior", {})
    normalization = data.get("normalization", {})

    theme = str(
        appearance.get("theme", "automatic")
    )

    if theme not in {"automatic", "light", "dark"}:
        theme = "automatic"

    selected_provider = str(
        providers.get(
            "selected",
            providers.get("primary", "apple_music"),
        )
    )

    provider_definition = PROVIDERS_BY_ID.get(
        selected_provider
    )

    if (
        provider_definition is None
        or provider_definition.status != "supported"
    ):
        selected_provider = "apple_music"

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
    )


def save_settings(
    settings: AppSettings,
    config_path: str | Path = "config.toml",
) -> None:
    path = Path(config_path)

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
        f'feature_handling = "{settings.feature_handling}"\n'
    )

    path.write_text(
        content,
        encoding="utf-8",
    )
