from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .diagnostics import is_frozen, user_data_dir
from .library_sources import MusicSource


def _default_config_path() -> Path:
    # Installierte Exe: benutzereigener, beschreibbarer Ordner. Sonst Repo.
    if is_frozen():
        return user_data_dir() / "config.toml"
    return Path(__file__).resolve().parents[2] / "config.toml"


DEFAULT_CONFIG_PATH = _default_config_path()

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

ThemeStyle = Literal[
    "standard",
    "apple",
]


@dataclass(frozen=True)
class AppSettings:
    theme: ThemeMode = "automatic"
    theme_style: ThemeStyle = "standard"
    language: str = "automatic"
    # Skaliert die App-Schrift zusaetzlich zur Windows-DPI-Skalierung.
    font_scale: float = 1.0
    # Muster für die Datei-Umbenennung (Platzhalter wie {track}, {title}).
    rename_pattern: str = "{track} - {title}"
    # Signierter Lizenzschlüssel (schaltet Premium-Funktionen frei). Leer =
    # Basisversion. Nicht geheim; wirkt nur mit gültiger Signatur.
    license_key: str = ""
    # Tag-Felder, die NICHT in die Dateien geschrieben werden (leer = alle an).
    disabled_tag_fields: tuple[str, ...] = ()
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
    # Album Gain exakt (ganzes Album am Stück dekodieren) statt schnell aus den
    # Track-Werten ableiten. Standard: schnell.
    audio_analysis_exact_album_gain: bool = False
    # Base64-kodierter Header-Zustand der Titelanalyse-Tabelle (Spaltenreihen-
    # folge/-breiten), damit die vom Nutzer sortierten Spalten erhalten bleiben.
    audio_analysis_column_state: str = ""

    music_sources: tuple[MusicSource, ...] = ()
    load_sources_on_startup: bool = True
    scan_sources_on_startup: bool = False

    discogs_token: str = ""
    tidal_client_id: str = ""
    spotify_client_id: str = ""
    # Akustischer Fingerabdruck (AcoustID). Leer = mitgelieferter App-Key.
    acoustid_api_key: str = ""
    # Optionaler Pfad zur fpcalc-Binärdatei (sonst Bundle/PATH).
    fpcalc_path: str = ""
    apple_request_interval_seconds: float = 1.0
    genius_request_interval_seconds: float = 1.0
    apple_web_search_enabled: bool = True
    # Quelle für die 30-Sekunden-Track-Vorschau: "deezer" oder "apple_music".
    preview_source: str = "deezer"


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
    network = data.get("network", {})
    rename = data.get("rename", {})
    license_section = data.get("license", {})
    metadata_section = data.get("metadata", {})
    raw_disabled = metadata_section.get("disabled_fields", [])
    disabled_tag_fields = tuple(
        str(name).strip()
        for name in (raw_disabled if isinstance(raw_disabled, list) else [])
        if str(name).strip()
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
    theme_style = str(
        appearance.get(
            "style",
            "standard",
        )
    )
    if language not in {
        "automatic",
        "de",
        "en",
        "es",
        "fr",
        "it",
        "pt_PT",
        "pt_BR",
    }:
        language = "automatic"

    font_scale = _safe_float(
        appearance.get("font_scale", 1.0),
        default=1.0,
        minimum=0.8,
        maximum=1.6,
    )

    if theme not in {
        "automatic",
        "light",
        "dark",
    }:
        theme = "automatic"
    if theme_style not in {
        "standard",
        "apple",
    }:
        theme_style = "standard"

    selected_provider = str(
        providers.get(
            "selected",
            "apple_music",
        )
    )
    provider = PROVIDERS_BY_ID.get(selected_provider)

    if provider is None or provider.status != "supported":
        selected_provider = "apple_music"

    selected_cover = str(
        cover.get(
            "selected",
            "apple_music",
        )
    )
    cover_provider = COVER_SOURCES_BY_ID.get(selected_cover)

    if cover_provider is None or cover_provider.status != "supported":
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
    exact_album_gain = bool(
        audio_analysis.get(
            "exact_album_gain",
            False,
        )
    )
    column_state = str(
        audio_analysis.get(
            "column_state",
            "",
        )
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
                    or Path(path_value).name
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
        theme_style=theme_style,
        language=language,
        font_scale=font_scale,
        rename_pattern=(
            str(rename.get("pattern", "{track} - {title}")).strip()
            or "{track} - {title}"
        ),
        license_key=str(license_section.get("key", "")).strip(),
        disabled_tag_fields=disabled_tag_fields,
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
        audio_analysis_exact_album_gain=exact_album_gain,
        audio_analysis_column_state=column_state,
        music_sources=tuple(music_sources),
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
        tidal_client_id=str(
            media_library.get(
                "tidal_client_id",
                "",
            )
        ).strip(),
        spotify_client_id=str(
            media_library.get(
                "spotify_client_id",
                "",
            )
        ).strip(),
        acoustid_api_key=str(
            media_library.get(
                "acoustid_api_key",
                "",
            )
        ).strip(),
        fpcalc_path=str(
            media_library.get(
                "fpcalc_path",
                "",
            )
        ).strip(),
        apple_request_interval_seconds=_safe_float(
            network.get("apple_request_interval_seconds", 1.0),
            default=1.0,
            minimum=0.5,
            maximum=10.0,
        ),
        genius_request_interval_seconds=_safe_float(
            network.get("genius_request_interval_seconds", 1.0),
            default=1.0,
            minimum=0.5,
            maximum=10.0,
        ),
        apple_web_search_enabled=bool(
            network.get(
                "apple_web_search_enabled",
                True,
            )
        ),
        preview_source=(
            "apple_music"
            if str(
                network.get("preview_source", "deezer")
            ).strip().lower()
            == "apple_music"
            else "deezer"
        ),
    )


def save_settings(
    settings: AppSettings,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> None:
    lines = [
        "[appearance]",
        f'theme = "{settings.theme}"',
        f'style = "{settings.theme_style}"',
        f'language = "{settings.language}"',
        f"font_scale = {settings.font_scale:.2f}",
        "",
        "[providers]",
        f'selected = "{settings.selected_provider}"',
        (f"enrich_missing_fields = {str(settings.enrich_missing_fields).lower()}"),
        f'apple_country = "{settings.apple_country.upper()}"',
        "",
        "[behavior]",
        (f"preview_before_writing = {str(settings.preview_before_writing).lower()}"),
        "",
        "[normalization]",
        f'feature_handling = "{settings.feature_handling}"',
        "",
        "[cover_sources]",
        f'selected = "{settings.selected_cover_source}"',
        (f"fallback_enabled = {str(settings.cover_fallback_enabled).lower()}"),
        f"minimum_size = {settings.minimum_cover_size}",
        (f"cache_max_age_days = {settings.cover_cache_max_age_days}"),
        "",
        "[cover_output]",
        'master_pattern = "{album_artist} - {album}.front.{ext}"',
        f"embedded_size = {settings.embedded_cover_size}",
        f"embedded_quality = {settings.embedded_cover_quality}",
        f"folder_size = {settings.folder_cover_size}",
        f"folder_quality = {settings.folder_cover_quality}",
        'folder_pattern = "{album_artist} - {album}_400px.jpg"',
        (f"artist_folder_levels_up = {settings.artist_folder_levels_up}"),
        "",
        "[audio_analysis]",
        (f"parallel_jobs = {settings.audio_analysis_parallel_jobs}"),
        (
            "exact_album_gain = "
            f"{str(settings.audio_analysis_exact_album_gain).lower()}"
        ),
        (
            "column_state = "
            f'"{_toml_string(settings.audio_analysis_column_state)}"'
        ),
        "",
        "[media_library]",
        f'discogs_token = "{_toml_string(settings.discogs_token)}"',
        f'tidal_client_id = "{_toml_string(settings.tidal_client_id)}"',
        f'spotify_client_id = "{_toml_string(settings.spotify_client_id)}"',
        f'acoustid_api_key = "{_toml_string(settings.acoustid_api_key)}"',
        f'fpcalc_path = "{_toml_string(settings.fpcalc_path)}"',
        "",
        "[network]",
        (
            "apple_request_interval_seconds = "
            f"{settings.apple_request_interval_seconds:.1f}"
        ),
        (
            "genius_request_interval_seconds = "
            f"{settings.genius_request_interval_seconds:.1f}"
        ),
        (
            "apple_web_search_enabled = "
            f"{str(settings.apple_web_search_enabled).lower()}"
        ),
        f'preview_source = "{_toml_string(settings.preview_source)}"',
        "",
        "[rename]",
        f'pattern = "{_toml_string(settings.rename_pattern)}"',
        "",
        "[license]",
        f'key = "{_toml_string(settings.license_key)}"',
        "",
        "[metadata]",
        (
            "disabled_fields = ["
            + ", ".join(
                f'"{_toml_string(name)}"' for name in settings.disabled_tag_fields
            )
            + "]"
        ),
        "",
        "[library]",
        (f"load_sources_on_startup = {str(settings.load_sources_on_startup).lower()}"),
        (f"scan_sources_on_startup = {str(settings.scan_sources_on_startup).lower()}"),
        "",
    ]

    for source in settings.music_sources:
        lines.extend(
            [
                "[[music_sources]]",
                f'id = "{_toml_string(source.source_id)}"',
                f'name = "{_toml_string(source.name)}"',
                f'path = "{_toml_string(source.path)}"',
                (f"enabled = {str(source.enabled).lower()}"),
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
    return (
        str(value)
        .replace(
            "\\",
            "\\\\",
        )
        .replace(
            '"',
            '\\"',
        )
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


def _safe_float(
    value: object,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def apply_request_intervals(settings: AppSettings) -> None:
    from .providers import apple_http, apple_music_web, genius

    apple_http.REQUEST_INTERVAL_SECONDS = settings.apple_request_interval_seconds
    genius.REQUEST_INTERVAL_SECONDS = settings.genius_request_interval_seconds
    apple_music_web.WEB_SEARCH_ENABLED = settings.apple_web_search_enabled
