from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


FeatureHandling = Literal[
    "artist_only",
    "title_and_artist",
    "source",
]


@dataclass(frozen=True)
class AppSettings:
    theme: str = "automatic"
    apple_music_enabled: bool = True
    musicbrainz_enabled: bool = True
    apple_country: str = "DE"
    preview_before_writing: bool = True
    feature_handling: FeatureHandling = "artist_only"


def load_settings(config_path: str | Path = "config.toml") -> AppSettings:
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

    feature_handling = normalization.get(
        "feature_handling",
        "artist_only",
    )

    if feature_handling not in {
        "artist_only",
        "title_and_artist",
        "source",
    }:
        feature_handling = "artist_only"

    return AppSettings(
        theme=str(appearance.get("theme", "automatic")),
        apple_music_enabled=bool(
            providers.get("apple_music_enabled", True)
        ),
        musicbrainz_enabled=bool(
            providers.get("musicbrainz_enabled", True)
        ),
        apple_country=str(
            providers.get("apple_country", "DE")
        ).upper(),
        preview_before_writing=bool(
            behavior.get("preview_before_writing", True)
        ),
        feature_handling=feature_handling,
    )
