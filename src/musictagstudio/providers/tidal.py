from __future__ import annotations

from base64 import b64encode
import threading
import time
from urllib.parse import quote, urlencode
from urllib.request import Request

from .. import __version__
from .oauth_catalog import CatalogProviderError, request_json
from .tidal_auth import get_user_access_token
from .streaming_catalog import (
    CatalogAlbumCandidate,
    album_confidence,
    optional_int,
)


TOKEN_ENDPOINT = "https://auth.tidal.com/v1/oauth2/token"
SEARCH_ENDPOINT = "https://openapi.tidal.com/v2/searchResults"
ALBUMS_ENDPOINT = "https://openapi.tidal.com/v2/albums"
JSON_API_MEDIA_TYPE = "application/vnd.api+json"
_token_lock = threading.Lock()
_cached_token = ""
_cached_credentials = ""
_token_expires_at = 0.0


def search_albums(
    album: str,
    artist: str,
    *,
    client_id: str,
    client_secret: str,
    country: str = "DE",
    expected_track_count: int | None = None,
    wanted_year: str = "",
    limit: int = 20,
) -> list[CatalogAlbumCandidate]:
    user_token = get_user_access_token(client_id)
    token = user_token
    if not token:
        token = _access_token(client_id, client_secret)
    query = " ".join(value for value in (artist, album) if value.strip())
    # TIDAL interprets a slash in the search resource identifier as a path
    # separator. Searching "1 2" instead of "1/2" returns the intended album
    # directly and still leaves the original title available for scoring.
    query = " ".join(query.replace("/", " ").split())
    search_params = urlencode(
        {
            "countryCode": country.upper(),
            "include": "albums",
            "limit": max(1, min(limit, 20)),
        }
    )
    search_request = Request(
        f"{SEARCH_ENDPOINT}/{quote(query, safe='')}?{search_params}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": JSON_API_MEDIA_TYPE,
            "Content-Type": JSON_API_MEDIA_TYPE,
            "User-Agent": f"MusicTagStudio/{__version__}",
        },
    )
    try:
        search_payload = request_json(search_request)
    except CatalogProviderError as error:
        if "HTTP 404" in str(error):
            connection = "Die TIDAL-Anmeldung ist gültig, aber " if user_token else ""
            raise CatalogProviderError(
                f"{connection}der öffentliche TIDAL-Katalog-Endpunkt ist "
                "derzeit nicht verfügbar (HTTP 404)."
            ) from error
        raise CatalogProviderError(f"TIDAL-Suche fehlgeschlagen: {error}") from error
    album_ids = _search_album_ids(search_payload)
    if not album_ids:
        return []
    album_params = urlencode(
        {
            "countryCode": country.upper(),
            "filter[id]": ",".join(album_ids[: max(1, min(limit, 20))]),
            "include": "artists",
        }
    )
    album_request = Request(
        f"{ALBUMS_ENDPOINT}?{album_params}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": JSON_API_MEDIA_TYPE,
            "Content-Type": JSON_API_MEDIA_TYPE,
            "User-Agent": f"MusicTagStudio/{__version__}",
        },
    )
    try:
        payload = request_json(album_request)
    except CatalogProviderError as error:
        raise CatalogProviderError(
            f"TIDAL-Albumdetails fehlgeschlagen: {error}"
        ) from error
    included = payload.get("included") or []
    artist_names = {
        str(item.get("id") or ""): str((item.get("attributes") or {}).get("name") or "")
        for item in included
        if isinstance(item, dict) and str(item.get("type") or "") == "artists"
    }
    candidates: list[CatalogAlbumCandidate] = []
    resources = payload.get("data") or []
    if isinstance(resources, dict):
        resources = [resources]
    resources = list(resources) + list(included)
    for item in resources:
        if not isinstance(item, dict) or str(item.get("type") or "") != "albums":
            continue
        attributes = item.get("attributes") or {}
        external_id = str(item.get("id") or "").strip()
        actual_album = str(
            attributes.get("title") or attributes.get("name") or ""
        ).strip()
        if not external_id or not actual_album:
            continue
        actual_artist = _album_artist(attributes, item, artist_names)
        actual_year = str(
            attributes.get("releaseDate") or attributes.get("release_date") or ""
        )[:4]
        track_count = (
            optional_int(attributes.get("numberOfTracks"))
            or optional_int(attributes.get("numberOfItems"))
            or optional_int(attributes.get("number_of_tracks"))
            or 0
        )
        external_url = str(
            attributes.get("url")
            or attributes.get("externalUrl")
            or _external_link(attributes)
            or f"https://tidal.com/browse/album/{external_id}"
        )
        candidates.append(
            CatalogAlbumCandidate(
                provider="tidal",
                external_id=external_id,
                external_url=external_url,
                album=actual_album,
                artist=actual_artist,
                year=actual_year,
                track_count=track_count,
                confidence=album_confidence(
                    wanted_album=album,
                    wanted_artist=artist,
                    wanted_year=wanted_year,
                    expected_track_count=expected_track_count,
                    album=actual_album,
                    artist=actual_artist,
                    year=actual_year,
                    track_count=track_count,
                ),
                country=country.upper(),
                quality=_media_quality_label(attributes),
            )
        )
    return sorted(
        candidates,
        key=lambda candidate: (-candidate.confidence, candidate.album.casefold()),
    )


# TIDAL-Kennzeichen (mediaTags/audioModes) -> lesbares Label. Höchste
# vorhandene Qualität gewinnt. Defensiv: verschiedene mögliche Feldnamen und
# sowohl Listen als auch Strings werden akzeptiert; Unbekanntes -> "".
_QUALITY_LABELS: tuple[tuple[str, str], ...] = (
    ("HIRES_LOSSLESS", "Hi-Res Lossless"),
    ("HI_RES_LOSSLESS", "Hi-Res Lossless"),
    ("HI_RES", "Hi-Res"),
    ("LOSSLESS", "Lossless"),
    ("DOLBY_ATMOS", "Dolby Atmos"),
    ("SONY_360RA", "360 Reality Audio"),
    ("MQA", "MQA"),
    ("HIGH", "High"),
    ("LOW", "Low"),
)


def _media_quality_label(attributes: dict) -> str:
    raw = (
        attributes.get("mediaTags")
        or attributes.get("audioModes")
        or attributes.get("audioQuality")
        or attributes.get("media_tags")
        or ""
    )
    if isinstance(raw, str):
        tokens = {raw.strip().upper()}
    elif isinstance(raw, (list, tuple)):
        tokens = {str(item).strip().upper() for item in raw}
    else:
        return ""
    for token, label in _QUALITY_LABELS:
        if token in tokens:
            return label
    return ""


def _external_link(attributes: dict) -> str:
    links = attributes.get("externalLinks") or []
    for link in links:
        if not isinstance(link, dict):
            continue
        href = str(link.get("href") or "").strip()
        if href.startswith("https://tidal.com/"):
            return href
    return ""


def _search_album_ids(payload: dict) -> list[str]:
    ids: list[str] = []
    included = payload.get("included") or []
    for item in included:
        if isinstance(item, dict) and str(item.get("type") or "") == "albums":
            album_id = str(item.get("id") or "").strip()
            if album_id and album_id not in ids:
                ids.append(album_id)
    data = payload.get("data") or {}
    relationship_data: list[object] = []
    if isinstance(data, dict):
        relationship_data = (
            ((data.get("relationships") or {}).get("albums") or {}).get("data")
        ) or []
    for item in relationship_data:
        if isinstance(item, dict):
            album_id = str(item.get("id") or "").strip()
            if album_id and album_id not in ids:
                ids.append(album_id)
    return ids


def _access_token(client_id: str, client_secret: str) -> str:
    global _cached_token, _cached_credentials, _token_expires_at
    if not client_id.strip() or not client_secret.strip():
        raise CatalogProviderError("TIDAL-Zugangsdaten fehlen.")
    credential_key = f"{client_id.strip()}:{client_secret.strip()}"
    with _token_lock:
        if (
            _cached_token
            and _cached_credentials == credential_key
            and time.monotonic() < _token_expires_at
        ):
            return _cached_token
    credentials = b64encode(
        f"{client_id.strip()}:{client_secret.strip()}".encode("utf-8")
    ).decode("ascii")
    request = Request(
        TOKEN_ENDPOINT,
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        payload = request_json(request)
    except CatalogProviderError as error:
        raise CatalogProviderError(
            f"TIDAL-Anmeldung fehlgeschlagen: {error}"
        ) from error
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise CatalogProviderError("TIDAL hat kein Zugriffstoken geliefert.")
    expires_in = optional_int(payload.get("expires_in")) or 3600
    with _token_lock:
        _cached_token = token
        _cached_credentials = credential_key
        _token_expires_at = time.monotonic() + max(60, expires_in - 60)
    return token


def validate_credentials(client_id: str, client_secret: str) -> None:
    user_token = get_user_access_token(client_id)
    if user_token:
        return
    _access_token(client_id, client_secret)


def _album_artist(
    attributes: dict,
    item: dict,
    artist_names: dict[str, str],
) -> str:
    artists = attributes.get("artists") or []
    names = [
        str(value.get("name") or "").strip()
        for value in artists
        if isinstance(value, dict) and str(value.get("name") or "").strip()
    ]
    if names:
        return ", ".join(names)
    relationship_data = ((item.get("relationships") or {}).get("artists") or {}).get(
        "data"
    ) or []
    names = [
        artist_names.get(str(value.get("id") or ""), "").strip()
        for value in relationship_data
        if isinstance(value, dict)
    ]
    return ", ".join(name for name in names if name)
