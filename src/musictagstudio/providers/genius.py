from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .. import __version__


SEARCH_ENDPOINT = "https://api.genius.com/search"
REQUEST_INTERVAL_SECONDS = 1.0
DETAIL_ENRICHMENT_LIMIT = 5
_request_lock = threading.Lock()
_last_request_started = 0.0


class GeniusProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeniusSongCandidate:
    genius_id: int
    title: str
    artist: str
    url: str
    album: str = ""
    cover_url: str = ""


def search_songs_by_text(
    text: str,
    *,
    access_token: str,
    limit: int = 20,
) -> list[GeniusSongCandidate]:
    query = " ".join(str(text or "").split())
    if len(query) < 3:
        raise ValueError("Bitte mindestens drei Zeichen des Liedtexts eingeben.")
    token = access_token.strip()
    if not token:
        return []

    request = Request(
        f"{SEARCH_ENDPOINT}?{urlencode({'q': query})}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": f"MusicTagStudio/{__version__}",
        },
    )
    payload = _request_json(request)

    hits = (payload.get("response") or {}).get("hits") or []
    candidates: list[GeniusSongCandidate] = []
    seen: set[int] = set()
    for hit in hits:
        if not isinstance(hit, dict) or hit.get("type") != "song":
            continue
        result = hit.get("result") or {}
        try:
            genius_id = int(result.get("id") or 0)
        except (TypeError, ValueError):
            genius_id = 0
        title = str(
            result.get("title_with_featured") or result.get("title") or ""
        ).strip()
        artist = str(result.get("artist_names") or "").strip()
        url = str(result.get("url") or "").strip()
        if not genius_id or not title or not artist or not url:
            continue
        if genius_id in seen:
            continue
        seen.add(genius_id)
        candidates.append(
            GeniusSongCandidate(
                genius_id=genius_id,
                title=title,
                artist=artist,
                url=url,
                album=_album_from_result(result),
                cover_url=str(
                    result.get("song_art_image_thumbnail_url")
                    or result.get("header_image_thumbnail_url")
                    or ""
                ).strip(),
            )
        )
        if len(candidates) >= max(1, min(limit, 50)):
            break
    detail_candidates = candidates[:DETAIL_ENRICHMENT_LIMIT]
    with ThreadPoolExecutor(
        max_workers=min(4, len(detail_candidates) or 1)
    ) as executor:
        enriched = list(
            executor.map(
                lambda candidate: _enrich_candidate(
                    candidate,
                    access_token=token,
                ),
                detail_candidates,
            )
        )
    return enriched + candidates[DETAIL_ENRICHMENT_LIMIT:]


def validate_access_token(access_token: str) -> None:
    token = access_token.strip()
    if not token:
        raise GeniusProviderError("Der Genius Client Access Token fehlt.")
    # Gegen den tatsächlich genutzten Such-Endpunkt prüfen. Der Account-Endpunkt
    # (/account) verlangt die OAuth-Berechtigung "me", die ein im Dashboard
    # erzeugtes Client Access Token nicht besitzt – er würde ein gültiges Token
    # fälschlich ablehnen. /search akzeptiert das Client Access Token so, wie es
    # die App später verwendet.
    request = Request(
        f"{SEARCH_ENDPOINT}?{urlencode({'q': 'test'})}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": f"MusicTagStudio/{__version__}",
        },
    )
    _request_json(request)


def _album_from_result(result: dict) -> str:
    album = result.get("album") or {}
    if not isinstance(album, dict):
        return ""
    return str(album.get("name") or "").strip()


def _enrich_candidate(
    candidate: GeniusSongCandidate,
    *,
    access_token: str,
) -> GeniusSongCandidate:
    if candidate.album:
        return candidate
    request = Request(
        f"https://api.genius.com/songs/{candidate.genius_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": f"MusicTagStudio/{__version__}",
        },
    )
    try:
        payload = _request_json(request)
    except GeniusProviderError:
        return candidate
    song = (payload.get("response") or {}).get("song") or {}
    if not isinstance(song, dict):
        return candidate
    album = _album_from_result(song)
    if not album:
        return candidate
    return GeniusSongCandidate(
        genius_id=candidate.genius_id,
        title=candidate.title,
        artist=candidate.artist,
        url=candidate.url,
        album=album,
        cover_url=candidate.cover_url,
    )


def _request_json(request: Request) -> dict:
    for attempt in range(2):
        _pace_request()
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 429 and attempt == 0:
                time.sleep(_retry_after(error))
                continue
            detail = _error_detail(error)
            if error.code in {401, 403}:
                suffix = f" ({detail})" if detail else ""
                raise GeniusProviderError(
                    f"Der Genius Client Access Token wurde abgelehnt{suffix}."
                ) from error
            suffix = f": {detail}" if detail else ""
            raise GeniusProviderError(
                f"Genius meldet HTTP {error.code}{suffix}."
            ) from error
        except URLError as error:
            raise GeniusProviderError(
                f"Genius ist momentan nicht erreichbar: {error.reason}"
            ) from error
        except (
            TimeoutError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise GeniusProviderError(
                "Genius lieferte eine ungültige oder unvollständige Antwort."
            ) from error
        if not isinstance(payload, dict):
            raise GeniusProviderError("Genius lieferte keine gültige JSON-Antwort.")
        return payload
    raise GeniusProviderError("Die Genius-Anfrage ist fehlgeschlagen.")


def _pace_request() -> None:
    global _last_request_started
    with _request_lock:
        delay = REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_started)
        if delay > 0:
            time.sleep(delay)
        _last_request_started = time.monotonic()


def _error_detail(error: HTTPError) -> str:
    """Liest den Grund aus der Genius-Fehlerantwort (z. B. 'invalid_token').

    Genius liefert bei 4xx meist JSON wie {"error": "invalid_token",
    "error_description": "..."} oder {"meta": {"message": "..."}}. Das macht
    aus dem generischen "abgelehnt" einen konkreten Hinweis.
    """
    try:
        body = error.read().decode("utf-8", "replace")
    except (AttributeError, OSError):
        return ""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body.strip()[:200]
    if not isinstance(data, dict):
        return ""
    for key in ("error_description", "error"):
        value = data.get(key)
        if value:
            return str(value)
    meta = data.get("meta")
    if isinstance(meta, dict) and meta.get("message"):
        return str(meta["message"])
    return ""


def _retry_after(error: HTTPError) -> float:
    try:
        value = float(error.headers.get("Retry-After", "2"))
    except (AttributeError, TypeError, ValueError):
        value = 2.0
    return max(1.0, min(value, 30.0))
