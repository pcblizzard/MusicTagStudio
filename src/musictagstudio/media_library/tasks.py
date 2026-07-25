from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
import urllib.error
import urllib.request

from .. import __version__
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


@dataclass(frozen=True)
class LiveArtistSuggestion:
    name: str
    correction: bool = False


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


def _fetch_live_artist_suggestions(
    controller, query: str
) -> list[LiveArtistSuggestion]:
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
    wanted = _normalized(query)
    has_direct_match = any(
        _normalized(name) == wanted or _normalized(name).startswith(wanted)
        for name in combined
    )
    correction_names: set[str] = set()
    if not has_direct_match:
        try:
            fuzzy = controller.search_artists(
                query,
                # The normal search deliberately asks MusicBrainz for a
                # broader candidate set than the compact suggestion panel.
                # Otherwise the intended artist can be hidden behind several
                # literal but obscure spelling matches (for example
                # ``Cluoes`` -> ``Clues`` instead of ``Clueso``).
                limit=25,
                preferred_country=load_settings().apple_country,
            ).artists
        except Exception:
            fuzzy = ()
        for artist in fuzzy:
            normalized_name = _normalized(artist.name)
            combined.append(artist.name)
            correction_names.add(normalized_name)
    unique: dict[str, str] = {}
    for name in combined:
        unique.setdefault(_normalized(name), name)
    ordered = sorted(
        unique.values(),
        key=lambda name: (
            0 if _normalized(name) == wanted
            else 1 if _normalized(name).startswith(wanted)
            else 2 if wanted in _normalized(name)
            else 3,
            0 if (
                _normalized(name)
                and wanted
                and _normalized(name)[0] == wanted[0]
            ) else 1,
            # A swapped pair of letters normally preserves the input length.
            # Prefer that over shorter/longer names which merely happen to
            # receive a slightly better SequenceMatcher score.
            abs(len(_normalized(name)) - len(wanted)),
            -SequenceMatcher(None, wanted, _normalized(name)).ratio(),
            name.casefold(),
        ),
    )[:8]
    return [
        LiveArtistSuggestion(
            name=name,
            correction=(
                _normalized(name) in correction_names
                and _normalized(name) != wanted
            ),
        )
        for name in ordered
    ]


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
                f"MusicTagStudio/{__version__} "
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
                f"MusicTagStudio/{__version__} "
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


def _fetch_release_group_cover(
    release_group_id: str,
    cache_directory: Path,
) -> bytes | None:
    """Load the representative Cover Art Archive image for a release group."""
    return _fetch_url_cover(
        (
            "https://coverartarchive.org/"
            f"release-group/{release_group_id}/front-250"
        ),
        cache_directory / f"release-group-{release_group_id}.jpg",
    )


def _fetch_release_group_cover_with_discogs(
    release_group_id: str,
    cache_directory: Path,
    artist: str,
    title: str,
    year: str,
    token: str,
) -> bytes | None:
    data = _fetch_release_group_cover(release_group_id, cache_directory)
    if data:
        return data
    return _fetch_matching_discogs_cover(
        cache_directory,
        artist,
        title,
        year,
        token,
    )


def _fetch_release_cover_with_discogs(
    release_id: str,
    cache_directory: Path,
    artist: str,
    title: str,
    year: str,
    token: str,
) -> bytes | None:
    data = _fetch_release_cover(release_id, cache_directory)
    if data:
        return data
    return _fetch_matching_discogs_cover(
        cache_directory,
        artist,
        title,
        year,
        token,
    )


def _fetch_matching_discogs_cover(
    cache_directory: Path,
    artist: str,
    title: str,
    year: str,
    token: str,
) -> bytes | None:
    if not token.strip() or not artist.strip() or not title.strip():
        return None
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
