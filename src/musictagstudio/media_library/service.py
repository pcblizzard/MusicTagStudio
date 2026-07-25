from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlencode

from .discogs import classify_release, release_badges

from ..providers.musicbrainz import (
    BASE_URL,
    _artist_credit,
    _request_json,
)


@dataclass(frozen=True)
class ArtistCandidate:
    artist_id: str
    name: str
    sort_name: str = ""
    disambiguation: str = ""
    country: str = ""
    artist_type: str = ""
    score: int = 0


@dataclass(frozen=True)
class ArtistSearchResult:
    query: str
    artists: tuple[ArtistCandidate, ...]
    used_fuzzy_search: bool = False



@dataclass(frozen=True)
class ReleaseGroup:
    release_group_id: str
    title: str
    first_release_date: str = ""
    primary_type: str = ""
    secondary_types: tuple[str, ...] = ()
    artist: str = ""
    edition_count: int = 0
    source: str = "musicbrainz"
    category: str = ""
    labels: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    badges: tuple[str, ...] = ()
    external_url: str = ""
    cover_url: str = ""
    discogs_release_id: int = 0
    discogs_contributions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Edition:
    release_id: str
    title: str
    date: str = ""
    country: str = ""
    status: str = ""
    barcode: str = ""
    label: str = ""
    format: str = ""
    medium_count: int = 0
    track_count: int = 0
    source: str = "musicbrainz"
    category: str = ""
    labels: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    badges: tuple[str, ...] = ()
    external_url: str = ""
    cover_url: str = ""
    discogs_release_id: int = 0


@dataclass(frozen=True)
class Track:
    disc_number: int
    track_number: int
    title: str
    artist: str = ""
    length_ms: int | None = None


def search_artists(
    query: str,
    *,
    limit: int = 25,
) -> list[ArtistCandidate]:
    return list(
        search_artists_with_fallback(
            query,
            limit=limit,
        ).artists
    )


def search_artists_with_fallback(
    query: str,
    *,
    limit: int = 25,
) -> ArtistSearchResult:
    query = str(
        query or ""
    ).strip()

    if not query:
        return ArtistSearchResult(
            query="",
            artists=(),
        )

    request_limit = max(
        1,
        min(
            limit,
            100,
        ),
    )

    normal_payload = _request_json(
        f"{BASE_URL}/artist?"
        + urlencode(
            {
                "query": _escape(
                    query
                ),
                "fmt": "json",
                "limit": request_limit,
            }
        )
    )
    normal_artists = _artist_candidates(
        normal_payload
    )

    wanted = _normalise_artist_name(
        query
    )
    exact_found = any(
        _normalise_artist_name(
            artist.name
        ) == wanted
        or _normalise_artist_name(
            artist.sort_name
        ) == wanted
        for artist in normal_artists
    )

    if normal_artists:
        return ArtistSearchResult(
            query=query,
            artists=tuple(
                normal_artists
            ),
            used_fuzzy_search=not exact_found,
        )

    fuzzy_terms = [
        f"{_escape(term)}~0.8"
        for term in re.findall(
            r"[\wÀ-ÖØ-öø-ÿ]+",
            query,
            flags=re.UNICODE,
        )
        if len(term) >= 3
    ]

    if not fuzzy_terms:
        return ArtistSearchResult(
            query=query,
            artists=(),
        )

    fuzzy_payload = _request_json(
        f"{BASE_URL}/artist?"
        + urlencode(
            {
                "query": " ".join(
                    fuzzy_terms
                ),
                "fmt": "json",
                "limit": request_limit,
            }
        )
    )

    return ArtistSearchResult(
        query=query,
        artists=tuple(
            _artist_candidates(
                fuzzy_payload
            )
        ),
        used_fuzzy_search=True,
    )


def _artist_candidates(
    payload: dict,
) -> list[ArtistCandidate]:
    artists: list[
        ArtistCandidate
    ] = []

    for item in payload.get(
        "artists",
        [],
    ):
        artist_id = str(
            item.get(
                "id",
                "",
            )
        )
        if not artist_id:
            continue

        artists.append(
            ArtistCandidate(
                artist_id=artist_id,
                name=str(
                    item.get(
                        "name",
                        "",
                    )
                ),
                sort_name=str(
                    item.get(
                        "sort-name",
                        "",
                    )
                ),
                disambiguation=str(
                    item.get(
                        "disambiguation",
                        "",
                    )
                ),
                country=str(
                    item.get(
                        "country",
                        "",
                    )
                ),
                artist_type=str(
                    item.get(
                        "type",
                        "",
                    )
                ),
                score=_safe_int(
                    item.get(
                        "score"
                    )
                ),
            )
        )

    return sorted(
        artists,
        key=lambda artist: (
            -artist.score,
            artist.name.casefold(),
        ),
    )


def _normalise_artist_name(
    value: str,
) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(
            value or ""
        ).casefold(),
    )



def _parse_release_groups(
    raw_groups: list[dict],
) -> list[ReleaseGroup]:
    groups: list[
        ReleaseGroup
    ] = []

    for item in raw_groups:
        group_id = str(
            item.get(
                "id",
                "",
            )
        )
        if not group_id:
            continue

        title = str(
            item.get(
                "title",
                "",
            )
        )
        primary_type = str(
            item.get(
                "primary-type",
                "",
            )
        )
        secondary_types = tuple(
            str(value)
            for value in item.get(
                "secondary-types",
                [],
            )
        )
        category = classify_release(
            title=title,
            primary_type=primary_type,
            secondary_types=secondary_types,
        )
        groups.append(
            ReleaseGroup(
                release_group_id=group_id,
                title=title,
                first_release_date=str(
                    item.get(
                        "first-release-date",
                        "",
                    )
                ),
                primary_type=primary_type,
                secondary_types=secondary_types,
                artist=_artist_credit(
                    item.get(
                        "artist-credit",
                        [],
                    )
                ),
                category=category,
                badges=release_badges(
                    category=category,
                ),
                external_url=(
                    "https://musicbrainz.org/release-group/"
                    + group_id
                ),
            )
        )

    return groups


def fetch_artist_release_groups(
    artist_id: str,
    *,
    limit: int = 100,
) -> list[ReleaseGroup]:
    groups: list[
        ReleaseGroup
    ] = []
    offset = 0

    while True:
        payload = _request_json(
            f"{BASE_URL}/release-group?"
            + urlencode(
                {
                    "artist": artist_id,
                    "fmt": "json",
                    "limit": min(
                        100,
                        max(
                            1,
                            limit,
                        ),
                    ),
                    "offset": offset,
                }
            )
        )
        raw_groups = payload.get(
            "release-groups",
            [],
        )

        groups.extend(
            _parse_release_groups(
                raw_groups
            )
        )

        offset += len(
            raw_groups
        )
        total = _safe_int(
            payload.get(
                "release-group-count"
            )
        )

        if (
            not raw_groups
            or offset >= total
            or offset >= limit
        ):
            break

    return sorted(
        groups,
        key=lambda group: (
            _type_order(
                group.primary_type
            ),
            group.first_release_date
            or "9999",
            group.title.casefold(),
        ),
    )


def fetch_release_group_editions(
    release_group_id: str,
) -> list[Edition]:
    payload = _request_json(
        f"{BASE_URL}/release?"
        + urlencode(
            {
                "release-group": (
                    release_group_id
                ),
                "inc": (
                    "media+labels+artist-credits"
                ),
                "fmt": "json",
                "limit": 100,
            }
        )
    )
    editions: list[
        Edition
    ] = []

    for item in payload.get(
        "releases",
        [],
    ):
        release_id = str(
            item.get(
                "id",
                "",
            )
        )

        if not release_id:
            continue

        media = item.get(
            "media",
            [],
        )
        labels = item.get(
            "label-info",
            [],
        )
        label = ""

        if labels:
            label = str(
                (
                    labels[0].get(
                        "label"
                    )
                    or {}
                ).get(
                    "name",
                    "",
                )
            )

        formats = [
            str(
                medium.get(
                    "format",
                    "",
                )
            )
            for medium in media
            if str(
                medium.get(
                    "format",
                    "",
                )
            ).strip()
        ]
        track_count = sum(
            _safe_int(
                medium.get(
                    "track-count"
                )
            )
            for medium in media
        )

        editions.append(
            Edition(
                release_id=release_id,
                title=str(
                    item.get(
                        "title",
                        "",
                    )
                ),
                date=str(
                    item.get(
                        "date",
                        "",
                    )
                ),
                country=str(
                    item.get(
                        "country",
                        "",
                    )
                ),
                status=str(
                    item.get(
                        "status",
                        "",
                    )
                ),
                barcode=str(
                    item.get(
                        "barcode",
                        "",
                    )
                    or ""
                ),
                label=label,
                format=", ".join(
                    dict.fromkeys(
                        formats
                    )
                ),
                medium_count=len(
                    media
                ),
                track_count=track_count,
                source="musicbrainz",
                category="",
                labels=(
                    (label,)
                    if label
                    else ()
                ),
                formats=tuple(
                    dict.fromkeys(
                        formats
                    )
                ),
                badges=release_badges(
                    formats=tuple(
                        dict.fromkeys(
                            formats
                        )
                    ),
                ),
                external_url=(
                    "https://musicbrainz.org/release/"
                    + release_id
                ),
            )
        )

    return sorted(
        editions,
        key=lambda edition: (
            0
            if edition.status.casefold()
            == "official"
            else 1,
            edition.date
            or "9999",
            edition.country,
            edition.track_count,
        ),
    )


def fetch_release_tracklist(
    release_id: str,
) -> list[Track]:
    payload = _request_json(
        f"{BASE_URL}/release/{release_id}?"
        + urlencode(
            {
                "inc": (
                    "recordings+artist-credits+media"
                ),
                "fmt": "json",
            }
        )
    )
    tracks: list[
        Track
    ] = []

    for disc_index, medium in enumerate(
        payload.get(
            "media",
            [],
        ),
        start=1,
    ):
        disc_number = (
            _safe_int(
                medium.get(
                    "position"
                )
            )
            or disc_index
        )

        for track_index, item in enumerate(
            medium.get(
                "tracks",
                [],
            ),
            start=1,
        ):
            recording = item.get(
                "recording",
                {},
            )
            tracks.append(
                Track(
                    disc_number=(
                        disc_number
                    ),
                    track_number=(
                        _safe_int(
                            item.get(
                                "position"
                            )
                        )
                        or track_index
                    ),
                    title=str(
                        item.get(
                            "title",
                            "",
                        )
                        or recording.get(
                            "title",
                            "",
                        )
                    ),
                    artist=_artist_credit(
                        item.get(
                            "artist-credit",
                            [],
                        )
                        or recording.get(
                            "artist-credit",
                            [],
                        )
                    ),
                    length_ms=(
                        _safe_int(
                            item.get(
                                "length"
                            )
                            or recording.get(
                                "length"
                            )
                        )
                        or None
                    ),
                )
            )

    return tracks


def _escape(
    value: str,
) -> str:
    return str(
        value
    ).replace(
        "\\",
        "\\\\",
    ).replace(
        '"',
        '\\"',
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


def _type_order(
    value: str,
) -> int:
    order = {
        "Album": 0,
        "EP": 1,
        "Single": 2,
        "Broadcast": 3,
        "Other": 4,
    }

    return order.get(
        value,
        9,
    )
