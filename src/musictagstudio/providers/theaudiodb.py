from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import html
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..diagnostics import project_root
from ..i18n import resolve_language
from .. import __version__


BASE_URL = "https://www.theaudiodb.com/api/v1/json/123"
USER_AGENT = f"MusicTagStudio/{__version__} (https://github.com/pcblizzard/MusicTagStudio)"
CACHE_SECONDS = 30 * 24 * 60 * 60


@dataclass(frozen=True)
class EditorialInfo:
    text: str
    source: str = "TheAudioDB"
    source_url: str = "https://www.theaudiodb.com/"
    language: str = "en"


def information_language(app_language: str) -> str:
    """Resolve automatic UI language and map unsupported texts to English."""
    return "de" if resolve_language(app_language) == "de" else "en"


def fetch_artist_info(artist: str, app_language: str) -> EditorialInfo | None:
    payload = _get_json("search.php", {"s": artist})
    rows = payload.get("artists") or []
    row = _best_row(rows, "strArtist", artist)
    return _info(row, "strBiography", information_language(app_language))


def fetch_album_info(
    artist: str,
    album: str,
    app_language: str,
) -> EditorialInfo | None:
    payload = _get_json("searchalbum.php", {"s": artist, "a": album})
    rows = payload.get("album") or []
    row = _best_row(rows, "strAlbum", album)
    return _info(row, "strDescription", information_language(app_language))


def fetch_album_info_with_apple_fallback(
    artist: str,
    album: str,
    app_language: str,
    apple_url: str = "",
) -> EditorialInfo | None:
    info = fetch_album_info(artist, album, app_language)
    if info is not None or not apple_url:
        return info
    # Local import avoids a provider import cycle.
    from .apple_editorial import fetch_apple_editorial

    return fetch_apple_editorial(apple_url, app_language)


def _best_row(rows, field: str, wanted: str) -> dict:
    valid = [row for row in rows if isinstance(row, dict)]
    wanted_key = _key(wanted)
    return next(
        (row for row in valid if _key(row.get(field, "")) == wanted_key),
        valid[0] if valid else {},
    )


def _info(row: dict, prefix: str, language: str) -> EditorialInfo | None:
    requested = language.upper()
    text = str(row.get(f"{prefix}{requested}") or "").strip()
    actual = language
    if not text and language != "en":
        text = str(row.get(f"{prefix}EN") or "").strip()
        actual = "en"
    text = _plain_text(text)
    if not text:
        return None
    entity_id = str(row.get("idArtist") or row.get("idAlbum") or "").strip()
    url = (
        f"https://www.theaudiodb.com/artist/{entity_id}"
        if row.get("idArtist") and not row.get("idAlbum")
        else "https://www.theaudiodb.com/"
    )
    return EditorialInfo(text=text, source_url=url, language=actual)


def _plain_text(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _get_json(endpoint: str, params: dict[str, str]) -> dict:
    url = f"{BASE_URL}/{endpoint}?{urlencode(params)}"
    cache_dir = project_root() / "cache" / "media_library" / "editorial"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{sha256(url.encode('utf-8')).hexdigest()}.json"
    if cache_path.is_file() and time.time() - cache_path.stat().st_mtime < CACHE_SECONDS:
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    try:
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return payload
