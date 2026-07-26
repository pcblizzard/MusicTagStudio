from __future__ import annotations

import threading
import time
from urllib.parse import urlencode
from urllib.request import Request

from .. import __version__
from .oauth_catalog import CatalogProviderError, request_json
from .streaming_catalog import (
    CatalogAlbumCandidate,
    album_confidence,
    album_core_title,
    optional_int,
)


TOKEN_ENDPOINT = "https://accounts.spotify.com/api/token"
SEARCH_ENDPOINT = "https://api.spotify.com/v1/search"
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
    limit: int = 10,
) -> list[CatalogAlbumCandidate]:
    token = _access_token(client_id, client_secret)
    # Ohne den Klammerzusatz suchen: Spotifys feldgebundene Phrasensuche
    # (album:"…") findet sonst z. B. „… (Live)" nicht, wenn MusicBrainz
    # „… (Live In Berlin)" führt. Das Scoring bewertet danach den vollen Titel.
    search_album = album_core_title(album)
    query = " ".join(
        value
        for value in (f'album:"{search_album}"', f'artist:"{artist}"')
        if value
    )
    params = urlencode(
        {
            "q": query,
            "type": "album",
            "market": country.upper(),
            "limit": max(1, min(limit, 10)),
        }
    )
    request = Request(
        f"{SEARCH_ENDPOINT}?{params}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": f"MusicTagStudio/{__version__}",
        },
    )
    payload = request_json(request)
    items = (payload.get("albums") or {}).get("items") or []
    candidates: list[CatalogAlbumCandidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        artists = item.get("artists") or []
        actual_artist = ", ".join(
            str(value.get("name") or "").strip()
            for value in artists
            if isinstance(value, dict) and str(value.get("name") or "").strip()
        )
        actual_album = str(item.get("name") or "").strip()
        external_id = str(item.get("id") or "").strip()
        if not external_id or not actual_album:
            continue
        actual_year = str(item.get("release_date") or "")[:4]
        track_count = optional_int(item.get("total_tracks")) or 0
        external_url = str(
            (item.get("external_urls") or {}).get("spotify")
            or f"https://open.spotify.com/album/{external_id}"
        )
        candidates.append(
            CatalogAlbumCandidate(
                provider="spotify",
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
            )
        )
    return sorted(
        candidates,
        key=lambda candidate: (-candidate.confidence, candidate.album.casefold()),
    )


def _access_token(client_id: str, client_secret: str) -> str:
    global _cached_token, _cached_credentials, _token_expires_at
    if not client_id.strip() or not client_secret.strip():
        raise CatalogProviderError("Spotify-Zugangsdaten fehlen.")
    credential_key = f"{client_id.strip()}:{client_secret.strip()}"
    with _token_lock:
        if (
            _cached_token
            and _cached_credentials == credential_key
            and time.monotonic() < _token_expires_at
        ):
            return _cached_token
    body = urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
        }
    ).encode("utf-8")
    request = Request(
        TOKEN_ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    payload = request_json(request)
    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise CatalogProviderError("Spotify hat kein Zugriffstoken geliefert.")
    expires_in = optional_int(payload.get("expires_in")) or 3600
    with _token_lock:
        _cached_token = token
        _cached_credentials = credential_key
        _token_expires_at = time.monotonic() + max(60, expires_in - 60)
    return token


def validate_credentials(client_id: str, client_secret: str) -> None:
    _access_token(client_id, client_secret)
