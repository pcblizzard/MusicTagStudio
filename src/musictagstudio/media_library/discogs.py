from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
import sqlite3
import threading
import time
from urllib.parse import quote, urlencode
import urllib.error
import urllib.request

from .. import __version__
from ..diagnostics import project_root

BASE_URL = "https://api.discogs.com"
USER_AGENT = (
    f"MusicTagStudio/{__version__} "
    "(https://github.com/pcblizzard/MusicTagStudio)"
)
REQUEST_INTERVAL_SECONDS = 1.05
_request_lock = threading.Lock()
_last_request_at = 0.0


class DiscogsProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class DiscogsArtist:
    artist_id: int
    title: str
    resource_url: str = ""
    thumb: str = ""


@dataclass(frozen=True)
class DiscogsCatalogHit:
    kind: str
    entity_id: int
    title: str
    subtitle: str = ""
    resource_url: str = ""
    external_url: str = ""
    thumb: str = ""
    year: str = ""


@dataclass(frozen=True)
class DiscogsRelease:
    source_id: str
    title: str
    year: str = ""
    role: str = ""
    release_type: str = ""
    main_release_id: int = 0
    master_id: int = 0
    release_id: int = 0
    external_url: str = ""
    resource_url: str = ""
    cover_url: str = ""
    labels: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    format_descriptions: tuple[str, ...] = ()
    artists: tuple[str, ...] = ()
    track_count: int = 0
    category: str = "Sonstiges"
    badges: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscogsTrack:
    position: str
    title: str
    artist: str = ""
    duration: str = ""


@dataclass(frozen=True)
class DiscogsCatalogSnapshot:
    releases: tuple[DiscogsRelease, ...]
    fetched_at: float
    from_cache: bool = False


def load_catalog_snapshot(query: str) -> DiscogsCatalogSnapshot | None:
    cache_path = _catalog_cache_path()
    if not cache_path.is_file():
        return None
    try:
        with sqlite3.connect(cache_path) as connection:
            row = connection.execute(
                "SELECT releases_json, fetched_at FROM discogs_catalog WHERE query_key = ?",
                (_key(query),),
            ).fetchone()
        if row is None:
            return None
        values = json.loads(row[0])
        releases = tuple(_release_from_cache(item) for item in values)
        return DiscogsCatalogSnapshot(
            releases=releases,
            fetched_at=float(row[1]),
            from_cache=True,
        )
    except (OSError, sqlite3.Error, json.JSONDecodeError, TypeError, ValueError):
        return None


def save_catalog_snapshot(
    query: str,
    releases: list[DiscogsRelease],
) -> DiscogsCatalogSnapshot:
    cache_path = _catalog_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    fetched_at = time.time()
    payload = json.dumps(
        [asdict(release) for release in releases],
        ensure_ascii=False,
    )
    with sqlite3.connect(cache_path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS discogs_catalog ("
            "query_key TEXT PRIMARY KEY, releases_json TEXT NOT NULL, fetched_at REAL NOT NULL)"
        )
        connection.execute(
            "INSERT INTO discogs_catalog(query_key, releases_json, fetched_at) VALUES (?, ?, ?) "
            "ON CONFLICT(query_key) DO UPDATE SET releases_json=excluded.releases_json, "
            "fetched_at=excluded.fetched_at",
            (_key(query), payload, fetched_at),
        )
    return DiscogsCatalogSnapshot(
        releases=tuple(releases),
        fetched_at=fetched_at,
        from_cache=False,
    )


def _catalog_cache_path():
    return project_root() / "cache" / "media_library" / "discogs_catalog.sqlite3"


def _release_from_cache(item: dict) -> DiscogsRelease:
    tuple_fields = {
        "labels", "formats", "format_descriptions", "artists", "badges"
    }
    values = {
        key: tuple(value) if key in tuple_fields else value
        for key, value in item.items()
    }
    return DiscogsRelease(**values)


def search_artists(
    query: str,
    token: str,
    *,
    limit: int = 20,
) -> list[DiscogsArtist]:
    _require_token(token)
    payload = _get_json(
        "/database/search",
        token,
        {
            "q": query,
            "type": "artist",
            "per_page": max(
                1,
                min(
                    limit,
                    100,
                ),
            ),
            "page": 1,
        },
    )
    artists: list[DiscogsArtist] = []

    for item in payload.get(
        "results",
        [],
    ):
        artist_id = _safe_int(
            item.get(
                "id"
            )
        )

        if not artist_id:
            continue

        artists.append(
            DiscogsArtist(
                artist_id=artist_id,
                title=str(
                    item.get(
                        "title",
                        "",
                    )
                ),
                resource_url=str(
                    item.get(
                        "resource_url",
                        "",
                    )
                ),
                thumb=str(
                    item.get(
                        "thumb",
                        "",
                    )
                ),
            )
        )

    return artists


def search_catalog(
    query: str,
    token: str,
    *,
    kinds: tuple[str, ...] = (
        "artist",
        "release",
        "master",
        "label",
    ),
    limit_per_kind: int = 15,
) -> list[DiscogsCatalogHit]:
    _require_token(token)
    hits: list[DiscogsCatalogHit] = []

    for kind in kinds:
        payload = _get_json(
            "/database/search",
            token,
            {
                "q": query,
                "type": kind,
                "per_page": max(
                    1,
                    min(
                        limit_per_kind,
                        50,
                    ),
                ),
                "page": 1,
            },
        )

        for item in payload.get(
            "results",
            [],
        ):
            entity_id = _safe_int(
                item.get(
                    "id"
                )
            )

            if not entity_id:
                continue

            title = str(
                item.get(
                    "title",
                    "",
                )
            ).strip()

            if not title:
                continue

            labels = tuple(
                str(value)
                for value in item.get(
                    "label",
                    [],
                )
                if str(value).strip()
            )
            formats = tuple(
                str(value)
                for value in item.get(
                    "format",
                    [],
                )
                if str(value).strip()
            )
            subtitle_parts = [
                str(
                    item.get(
                        "year",
                        "",
                    )
                ).strip(),
                ", ".join(
                    labels[:2]
                ),
                ", ".join(
                    formats[:3]
                ),
            ]
            external_url = ""

            if kind == "artist":
                external_url = (
                    f"https://www.discogs.com/artist/{entity_id}"
                )
            elif kind == "label":
                external_url = (
                    f"https://www.discogs.com/label/{entity_id}"
                )
            elif kind == "master":
                external_url = (
                    f"https://www.discogs.com/master/{entity_id}"
                )
            else:
                external_url = (
                    f"https://www.discogs.com/release/{entity_id}"
                )

            hits.append(
                DiscogsCatalogHit(
                    kind=kind,
                    entity_id=entity_id,
                    title=title,
                    subtitle=" · ".join(
                        value
                        for value in subtitle_parts
                        if value
                    ),
                    resource_url=str(
                        item.get(
                            "resource_url",
                            "",
                        )
                    ),
                    external_url=external_url,
                    thumb=str(
                        item.get(
                            "thumb",
                            "",
                        )
                    ),
                    year=str(
                        item.get(
                            "year",
                            "",
                        )
                    ),
                )
            )

    kind_order = {
        "artist": 0,
        "release": 1,
        "master": 1,
        "label": 2,
    }

    return sorted(
        hits,
        key=lambda hit: (
            kind_order.get(
                hit.kind,
                99,
            ),
            _search_rank(
                query,
                hit.title,
            ),
            hit.title.casefold(),
        ),
    )


def fetch_artist_image(
    artist: str,
    token: str,
) -> tuple[str, str] | None:
    """Return the primary Discogs artist image and its source page."""
    if not str(token or "").strip():
        return None
    wanted = _key(artist)
    hits = search_catalog(
        artist,
        token,
        kinds=("artist",),
        limit_per_kind=15,
    )
    exact = [
        hit
        for hit in hits
        if _key(re.sub(r"\s+\(\d+\)$", "", hit.title)) == wanted
    ]
    if not exact:
        return None
    hit = exact[0]
    detail = _get_json(f"/artists/{hit.entity_id}", token)
    images = [
        image
        for image in detail.get("images", [])
        if isinstance(image, dict)
    ]
    images.sort(key=lambda image: 0 if image.get("type") == "primary" else 1)
    for image in images:
        url = str(image.get("uri") or image.get("resource_url") or "").strip()
        if url:
            return url, hit.external_url
    if hit.thumb:
        return hit.thumb, hit.external_url
    return None


def fetch_catalog_release(
    kind: str,
    entity_id: int,
    token: str,
) -> DiscogsRelease:
    _require_token(token)
    kind = str(
        kind or ""
    ).casefold()

    if kind == "master":
        master = _get_json(
            f"/masters/{entity_id}",
            token,
        )
        main_release = _safe_int(
            master.get(
                "main_release"
            )
        )

        if not main_release:
            raise DiscogsProviderError(
                "Der Discogs-Master besitzt keine Hauptausgabe."
            )

        detail = _get_json(
            f"/releases/{main_release}",
            token,
        )
        summary = {
            "id": entity_id,
            "main_release": main_release,
            "type": "master",
            "title": master.get(
                "title",
                detail.get(
                    "title",
                    "",
                ),
            ),
            "year": master.get(
                "year",
                detail.get(
                    "year",
                    "",
                ),
            ),
            "role": "Main",
        }
        return _release_from_payload(
            summary,
            detail,
        )

    detail = _get_json(
        f"/releases/{entity_id}",
        token,
    )
    summary = {
        "id": entity_id,
        "type": "release",
        "title": detail.get(
            "title",
            "",
        ),
        "year": detail.get(
            "year",
            "",
        ),
        "role": "Main",
    }

    return _release_from_payload(
        summary,
        detail,
    )


def fetch_label_releases(
    label_id: int,
    token: str,
    *,
    maximum: int = 250,
    label_name: str = "",
) -> list[DiscogsRelease]:
    _require_token(token)
    summaries: list[dict] = []
    page = 1

    while len(summaries) < maximum:
        payload = _get_json(
            f"/labels/{label_id}/releases",
            token,
            {
                "per_page": 100,
                "page": page,
            },
        )
        items = list(
            payload.get(
                "releases",
                [],
            )
        )
        summaries.extend(
            items
        )
        pages = _safe_int(
            (
                payload.get(
                    "pagination"
                )
                or {}
            ).get(
                "pages"
            )
        )

        if (
            not items
            or page >= pages
            or len(summaries) >= maximum
        ):
            break

        page += 1

    releases = [
        _release_from_label_summary(item, label_name)
        for item in summaries[:maximum]
        if _safe_int(item.get("id"))
    ]

    return _deduplicate_releases(
        releases
    )


def _release_from_label_summary(
    item: dict,
    label_name: str = "",
) -> DiscogsRelease:
    release_id = _safe_int(item.get("id"))
    title = str(item.get("title", "")).strip()
    formats = tuple(
        part.strip()
        for part in str(item.get("format", "")).split(",")
        if part.strip()
    )
    artist = _clean_artist_name(str(item.get("artist", "")).strip())
    category = classify_release(
        title=title,
        primary_type="release",
        formats=formats,
        descriptions=formats,
        artist_count=1 if artist else 0,
        label_count=1 if label_name else 0,
        role="Main",
    )
    return DiscogsRelease(
        source_id=f"discogs:{release_id}",
        title=title,
        year=str(item.get("year", "") or ""),
        role="Main",
        release_type="release",
        release_id=release_id,
        external_url=f"https://www.discogs.com/release/{release_id}",
        resource_url=str(item.get("resource_url", "")),
        cover_url=str(item.get("thumb", "")),
        labels=(label_name,) if label_name else (),
        formats=formats,
        format_descriptions=formats,
        artists=(artist,) if artist else (),
        category=category,
        badges=release_badges(
            formats=formats,
            descriptions=formats,
            category=category,
        ),
    )


def fetch_artist_releases(
    artist_id: int,
    token: str,
    *,
    maximum: int = 250,
) -> list[DiscogsRelease]:
    _require_token(token)
    summaries: list[dict] = []
    page = 1

    while len(summaries) < maximum:
        payload = _get_json(
            f"/artists/{artist_id}/releases",
            token,
            {
                "sort": "year",
                "sort_order": "asc",
                "per_page": 100,
                "page": page,
            },
        )
        page_items = list(
            payload.get(
                "releases",
                [],
            )
        )
        summaries.extend(
            page_items
        )
        pages = _safe_int(
            (
                payload.get(
                    "pagination"
                )
                or {}
            ).get(
                "pages"
            )
        )

        if (
            not page_items
            or page >= pages
            or len(summaries) >= maximum
        ):
            break

        page += 1

    releases: list[DiscogsRelease] = []

    for summary in summaries[:maximum]:
        role = str(
            summary.get(
                "role",
                "",
            )
        )

        if role and role.casefold() not in {
            "main",
            "appearance",
        }:
            continue

        detail = _fetch_summary_detail(
            summary,
            token,
        )
        releases.append(
            _release_from_payload(
                summary,
                detail,
            )
        )

    return _deduplicate_releases(
        releases
    )


def fetch_release_tracks(
    release_id: int,
    token: str,
) -> tuple[
    tuple[DiscogsTrack, ...],
    dict,
]:
    _require_token(token)
    payload = _get_json(
        f"/releases/{release_id}",
        token,
    )
    tracks: list[DiscogsTrack] = []

    for item in payload.get(
        "tracklist",
        [],
    ):
        item_type = str(
            item.get(
                "type_",
                "track",
            )
        ).casefold()

        if item_type not in {
            "track",
            "index",
        }:
            continue

        artists = tuple(
            str(
                artist.get(
                    "name",
                    "",
                )
            )
            for artist in item.get(
                "artists",
                [],
            )
            if str(
                artist.get(
                    "name",
                    "",
                )
            ).strip()
        )
        tracks.append(
            DiscogsTrack(
                position=str(
                    item.get(
                        "position",
                        "",
                    )
                ),
                title=str(
                    item.get(
                        "title",
                        "",
                    )
                ),
                artist=", ".join(
                    artists
                ),
                duration=str(
                    item.get(
                        "duration",
                        "",
                    )
                ),
            )
        )

    return (
        tuple(
            tracks
        ),
        payload,
    )


def _fetch_summary_detail(
    summary: dict,
    token: str,
) -> dict:
    release_type = str(
        summary.get(
            "type",
            "",
        )
    ).casefold()
    main_release = _safe_int(
        summary.get(
            "main_release"
        )
    )
    summary_id = _safe_int(
        summary.get(
            "id"
        )
    )

    try:
        if (
            release_type == "master"
            and main_release
        ):
            return _get_json(
                f"/releases/{main_release}",
                token,
            )

        if summary_id:
            return _get_json(
                f"/releases/{summary_id}",
                token,
            )
    except DiscogsProviderError:
        return {}

    return {}


def _release_from_payload(
    summary: dict,
    detail: dict,
) -> DiscogsRelease:
    release_type = str(
        summary.get(
            "type",
            "",
        )
    )
    summary_id = _safe_int(
        summary.get(
            "id"
        )
    )
    main_release_id = _safe_int(
        summary.get(
            "main_release"
        )
    )
    release_id = (
        main_release_id
        if release_type.casefold()
        == "master"
        and main_release_id
        else summary_id
    )
    title = str(
        summary.get(
            "title",
            "",
        )
        or detail.get(
            "title",
            "",
        )
    )
    year_value = (
        summary.get(
            "year"
        )
        or detail.get(
            "year"
        )
        or ""
    )
    labels = tuple(
        dict.fromkeys(
            str(
                label.get(
                    "name",
                    "",
                )
            )
            for label in detail.get(
                "labels",
                [],
            )
            if str(
                label.get(
                    "name",
                    "",
                )
            ).strip()
        )
    )
    artists = tuple(
        dict.fromkeys(
            _clean_artist_name(
                str(
                    artist.get(
                        "name",
                        "",
                    )
                )
            )
            for artist in detail.get(
                "artists",
                [],
            )
            if str(
                artist.get(
                    "name",
                    "",
                )
            ).strip()
        )
    )
    formats: list[str] = []
    descriptions: list[str] = []

    for format_item in detail.get(
        "formats",
        [],
    ):
        name = str(
            format_item.get(
                "name",
                "",
            )
        ).strip()
        quantity = str(
            format_item.get(
                "qty",
                "",
            )
        ).strip()

        if name:
            formats.append(
                (
                    f"{quantity}×{name}"
                    if quantity
                    and quantity != "1"
                    else name
                )
            )

        descriptions.extend(
            str(value)
            for value in format_item.get(
                "descriptions",
                [],
            )
            if str(
                value
            ).strip()
        )

    category = classify_release(
        title=title,
        primary_type=str(
            summary.get(
                "type",
                "",
            )
        ),
        formats=tuple(
            formats
        ),
        descriptions=tuple(
            descriptions
        ),
        artist_count=len(
            artists
        ),
        label_count=len(
            labels
        ),
        role=str(
            summary.get(
                "role",
                "",
            )
        ),
    )
    badges = release_badges(
        formats=tuple(
            formats
        ),
        descriptions=tuple(
            descriptions
        ),
        category=category,
    )
    images = detail.get(
        "images",
        [],
    )
    cover_url = ""

    for image in images:
        if str(
            image.get(
                "type",
                "",
            )
        ).casefold() == "primary":
            cover_url = str(
                image.get(
                    "uri150",
                    "",
                )
                or image.get(
                    "uri",
                    "",
                )
            )
            break

    if not cover_url and images:
        cover_url = str(
            images[0].get(
                "uri150",
                "",
            )
            or images[0].get(
                "uri",
                "",
            )
        )

    return DiscogsRelease(
        source_id=(
            f"discogs:{release_id or summary_id}"
        ),
        title=title,
        year=str(
            year_value
        ),
        role=str(
            summary.get(
                "role",
                "",
            )
        ),
        release_type=release_type,
        main_release_id=main_release_id,
        master_id=(
            summary_id
            if release_type.casefold()
            == "master"
            else 0
        ),
        release_id=release_id,
        external_url=(
            f"https://www.discogs.com/release/{release_id}"
            if release_id
            else ""
        ),
        resource_url=str(
            summary.get(
                "resource_url",
                "",
            )
        ),
        cover_url=cover_url,
        labels=labels,
        formats=tuple(
            dict.fromkeys(
                formats
            )
        ),
        format_descriptions=tuple(
            dict.fromkeys(
                descriptions
            )
        ),
        artists=artists,
        track_count=len(
            detail.get(
                "tracklist",
                [],
            )
        ),
        category=category,
        badges=badges,
    )


def classify_release(
    *,
    title: str,
    primary_type: str = "",
    secondary_types: tuple[str, ...] = (),
    formats: tuple[str, ...] = (),
    descriptions: tuple[str, ...] = (),
    artist_count: int = 0,
    label_count: int = 0,
    role: str = "",
) -> str:
    text = " ".join(
        (
            title,
            primary_type,
            *secondary_types,
            *formats,
            *descriptions,
            role,
        )
    ).casefold()
    compact = re.sub(
        r"[^a-z0-9]+",
        "",
        text,
    )

    if any(
        token in compact
        for token in (
            "mixtape",
            "streettape",
            "streetalbum",
        )
    ):
        return "Mixtapes"

    if "bootleg" in text or "unofficial" in text:
        return "Bootlegs"

    if "soundtrack" in text or "score" in text:
        return "Soundtracks"

    if (
        "box set" in text
        or "boxset" in compact
    ):
        return "Boxsets"

    if "live" in text:
        return "Live"

    multi_artist = artist_count > 1

    if multi_artist and label_count == 1:
        return "Sampler"

    if multi_artist and label_count > 1:
        return "Compilations"

    if "compilation" in text:
        return "Compilations"

    if re.search(
        r"\bep\b",
        text,
    ):
        return "EPs"

    if "single" in text:
        return "Singles"

    if "album" in text or "master" in text:
        return "Alben"

    return "Sonstiges"


def release_badges(
    *,
    formats: tuple[str, ...] = (),
    descriptions: tuple[str, ...] = (),
    category: str = "",
) -> tuple[str, ...]:
    values = [
        *formats,
        *descriptions,
    ]
    badges: list[str] = []

    for value in values:
        clean = str(
            value
        ).strip()

        if not clean:
            continue

        lower = clean.casefold()

        if lower in {
            "album",
            "single",
            "ep",
            "compilation",
        }:
            continue

        if clean not in badges:
            badges.append(
                clean
            )

    if category in {
        "Mixtapes",
        "Sampler",
        "Compilations",
        "Live",
        "Soundtracks",
        "Boxsets",
        "Bootlegs",
    }:
        badges.insert(
            0,
            category.rstrip(
                "s"
            ),
        )

    return tuple(
        badges[:8]
    )


def _deduplicate_releases(
    releases: list[DiscogsRelease],
) -> list[DiscogsRelease]:
    unique: dict[
        tuple[str, str, str],
        DiscogsRelease,
    ] = {}

    for release in releases:
        key = (
            _key(
                release.title
            ),
            release.year,
            release.category,
        )
        current = unique.get(
            key
        )

        if (
            current is None
            or (
                not current.cover_url
                and release.cover_url
            )
        ):
            unique[key] = release

    return sorted(
        unique.values(),
        key=lambda release: (
            _category_order(
                release.category
            ),
            release.year
            or "9999",
            release.title.casefold(),
        ),
    )


def _search_rank(
    query: str,
    title: str,
) -> tuple[int, int]:
    wanted = _key(
        query
    )
    actual = _key(
        title
    )

    if actual == wanted:
        return (
            0,
            0,
        )

    if actual.startswith(
        wanted
    ):
        return (
            1,
            len(
                actual
            ),
        )

    if wanted in actual:
        return (
            2,
            len(
                actual
            ),
        )

    return (
        3,
        len(
            actual
        ),
    )


def _get_json(
    endpoint: str,
    token: str,
    params: dict | None = None,
) -> dict:
    query = dict(
        params
        or {}
    )
    url = (
        BASE_URL
        + endpoint
        + "?"
        + urlencode(
            query
        )
    )
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Authorization": f"Discogs token={token}",
            "Accept": (
                "application/vnd.discogs.v2.discogs+json"
            ),
        },
    )

    for attempt in range(2):
        global _last_request_at
        with _request_lock:
            delay = REQUEST_INTERVAL_SECONDS - (
                time.monotonic() - _last_request_at
            )
            if delay > 0:
                time.sleep(delay)
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=20,
                ) as response:
                    return json.loads(
                        response.read().decode(
                            "utf-8"
                        )
                    )
            except urllib.error.HTTPError as error:
                if error.code == 429 and attempt == 0:
                    retry_after = float(
                        (error.headers or {}).get("Retry-After", "2")
                    )
                    time.sleep(max(1.0, min(retry_after, 30.0)))
                    continue
                if error.code in {
                    401,
                    403,
                }:
                    raise DiscogsProviderError(
                        "Discogs hat den Zugriff abgelehnt. "
                        "Bitte den persönlichen Discogs-Token in "
                        "den Einstellungen prüfen."
                    ) from error
                if error.code == 429:
                    raise DiscogsProviderError(
                        "Das Discogs-Anfragelimit ist erreicht. "
                        "Bitte die Suche in Kürze erneut versuchen."
                    ) from error
                raise DiscogsProviderError(
                    f"Discogs-Fehler HTTP {error.code}."
                ) from error
            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
            ) as error:
                raise DiscogsProviderError(
                    "Discogs konnte nicht erreicht oder die Antwort "
                    "nicht verarbeitet werden."
                ) from error
            finally:
                _last_request_at = time.monotonic()


def _require_token(
    token: str,
) -> None:
    if not str(
        token or ""
    ).strip():
        raise DiscogsProviderError(
            "Für die Discogs-Ergänzung ist ein persönlicher "
            "Discogs-Token erforderlich."
        )


def _clean_artist_name(
    value: str,
) -> str:
    return re.sub(
        r"\s+\(\d+\)$",
        "",
        value,
    ).strip()


def _key(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(
            value or ""
        ).casefold(),
    )


def _safe_int(
    value,
) -> int:
    try:
        return int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def _category_order(
    category: str,
) -> int:
    order = {
        "Alben": 0,
        "Live": 1,
        "EPs": 2,
        "Singles": 3,
        "Mixtapes": 4,
        "Sampler": 5,
        "Compilations": 6,
        "Soundtracks": 7,
        "Boxsets": 8,
        "Bootlegs": 9,
        "Sonstiges": 10,
    }

    return order.get(
        category,
        99,
    )
