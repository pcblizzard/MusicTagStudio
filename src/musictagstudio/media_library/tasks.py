from __future__ import annotations

from pathlib import Path
import re
import urllib.error
import urllib.request

from .discogs import (
    DiscogsCatalogHit,
    DiscogsCatalogSnapshot,
    fetch_artist_releases as fetch_discogs_artist_releases,
    fetch_label_releases,
    load_catalog_snapshot,
    save_catalog_snapshot,
    search_catalog,
)
from .presentation import normalized as _normalized
from ..providers.deezer import suggest_artists as suggest_deezer_artists
from ..settings import load_settings


def _search_exact_discogs_catalog(
    query: str,
    token: str,
) -> list[DiscogsCatalogHit]:
    wanted = _normalized(query)
    hits = search_catalog(
        query,
        token,
        kinds=("artist", "label", "master", "release"),
        limit_per_kind=15,
    )
    direct = [
        hit
        for hit in hits
        if wanted in {
            _normalized(hit.title),
            _normalized(_discogs_release_title(hit.title)),
        }
    ]
    if direct:
        return direct
    return [
        hit
        for hit in hits
        if _normalized(_discogs_entity_name(hit.title)) == wanted
    ]


def _fetch_discogs_hit_catalog(
    hit: DiscogsCatalogHit,
    query: str,
    token: str,
) -> DiscogsCatalogSnapshot:
    cached = load_catalog_snapshot(query)
    if cached is not None:
        return cached
    if hit.kind == "label":
        releases = fetch_label_releases(
            hit.entity_id,
            token,
            maximum=100,
            label_name=hit.title,
        )
    else:
        releases = fetch_discogs_artist_releases(
            hit.entity_id,
            token,
            maximum=100,
        )
    return save_catalog_snapshot(query, releases)


def _fetch_discogs_catalog(
    entity_name: str,
    token: str,
    *,
    force_refresh: bool = False,
) -> DiscogsCatalogSnapshot:
    if not force_refresh:
        cached = load_catalog_snapshot(entity_name)
        if cached is not None:
            return cached
    hits = search_catalog(
        entity_name,
        token,
        kinds=("artist", "label"),
        limit_per_kind=10,
    )
    wanted = _normalized(entity_name)
    exact_hits = [
        hit
        for hit in hits
        if _normalized(_discogs_entity_name(hit.title)) == wanted
    ]
    if not exact_hits:
        return save_catalog_snapshot(entity_name, [])
    # A label is the more specific interpretation when Discogs contains both
    # an artist and a label with exactly the requested name.
    hit = min(exact_hits, key=lambda item: 0 if item.kind == "label" else 1)
    if hit.kind == "label":
        releases = fetch_label_releases(
            hit.entity_id,
            token,
            maximum=100,
            label_name=hit.title,
        )
    else:
        releases = fetch_discogs_artist_releases(
            hit.entity_id, token, maximum=100
        )
    return save_catalog_snapshot(entity_name, releases)


def _discogs_entity_name(value: str) -> str:
    return re.sub(r"\s+\(\d+\)$", "", str(value or "")).strip()


def _discogs_release_title(value: str) -> str:
    text = str(value or "").strip()
    return text.split(" - ", 1)[-1].strip()


def _fetch_live_artist_suggestions(controller, query: str) -> list[str]:
    try:
        musicbrainz = controller.suggest_artists(
            query,
            limit=8,
            preferred_country=load_settings().apple_country,
        ).artists
    except Exception:
        musicbrainz = ()
    deezer = suggest_deezer_artists(query, limit=25)
    combined = [item.name for item in deezer]
    combined.extend(artist.name for artist in musicbrainz)
    return list(dict.fromkeys(combined))[:8]


def _fetch_url_cover(
    url: str,
    cache_path: Path,
) -> bytes | None:
    if cache_path.is_file():
        try:
            return cache_path.read_bytes()
        except OSError:
            pass

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "MusicTagStudio/0.7.3.0 "
                "(https://github.com/pcblizzard/MusicTagStudio)"
            )
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=12,
        ) as response:
            data = response.read()
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
    ):
        return None

    if data:
        try:
            cache_path.write_bytes(
                data
            )
        except OSError:
            pass

    return data or None


def _fetch_release_cover(
    release_id: str,
    cache_directory: Path,
) -> bytes | None:
    cache_path = (
        cache_directory
        / f"{release_id}.jpg"
    )

    if cache_path.is_file():
        try:
            return cache_path.read_bytes()
        except OSError:
            pass

    request = urllib.request.Request(
        (
            "https://coverartarchive.org/"
            f"release/{release_id}/front-250"
        ),
        headers={
            "User-Agent": (
                "MusicTagStudio/0.7.2.1 "
                "(https://github.com/pcblizzard/MusicTagStudio)"
            )
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=12,
        ) as response:
            data = response.read()
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
    ):
        return None

    if not data:
        return None

    try:
        cache_path.write_bytes(
            data
        )
    except OSError:
        pass

    return data


def _fetch_release_cover_with_discogs(
    release_id: str,
    cache_directory: Path,
    artist: str,
    title: str,
    year: str,
    token: str,
) -> bytes | None:
    data = _fetch_release_cover(release_id, cache_directory)
    if data or not token.strip() or not artist.strip() or not title.strip():
        return data
    try:
        hits = search_catalog(
            f"{artist} {title}",
            token,
            kinds=("master", "release"),
            limit_per_kind=12,
        )
    except Exception:
        return None
    wanted_title = _normalized(title)
    wanted_artist = _normalized(artist)
    wanted_year = str(year or "")[:4]
    for hit in hits:
        hit_title = _discogs_release_title(hit.title)
        credit = hit.title.split(" - ", 1)[0]
        if _normalized(hit_title) != wanted_title:
            continue
        if wanted_artist not in _normalized(credit):
            continue
        if wanted_year and hit.year and hit.year[:4] != wanted_year:
            continue
        if not hit.thumb:
            continue
        return _fetch_url_cover(
            hit.thumb,
            cache_directory / f"discogs-fallback-{hit.kind}-{hit.entity_id}.jpg",
        )
    return None
