from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .. import __version__
from .apple_editorial import _get_page
from .theaudiodb import information_language


SEARCH_ENDPOINT = "https://itunes.apple.com/search"
USER_AGENT = f"MusicTagStudio/{__version__}"


@dataclass(frozen=True)
class ArtistArtwork:
    data: bytes
    artist_url: str
    image_url: str
    source: str


def fetch_artist_artwork(
    artist: str,
    country: str,
    app_language: str,
    cache_directory: str | Path,
    discogs_token: str = "",
) -> ArtistArtwork | None:
    artist_url = _search_artist_url(artist, country, app_language)
    image_url = ""
    if artist_url:
        language = information_language(app_language)
        locale = "de-DE" if language == "de" else "en-GB"
        page_url = f"{artist_url}{'&' if '?' in artist_url else '?'}l={locale}"
        try:
            page = _get_page(page_url, language)
        except (HTTPError, URLError, TimeoutError, OSError):
            page = ""
        image_url = extract_artist_hero_url(page)
    if image_url:
        data = _download_image(image_url, cache_directory)
        if data:
            return ArtistArtwork(data, artist_url, image_url, "Apple Music")

    if not str(discogs_token or "").strip():
        return None
    try:
        from ..media_library.discogs import (
            DiscogsProviderError,
            fetch_artist_image,
        )

        discogs_image = fetch_artist_image(artist, discogs_token)
    except (DiscogsProviderError, HTTPError, URLError, TimeoutError, OSError):
        return None
    if discogs_image is None:
        return None
    image_url, artist_url = discogs_image
    if not _is_discogs_image_url(image_url):
        return None
    data = _download_image(image_url, cache_directory)
    if not data:
        return None
    return ArtistArtwork(data, artist_url, image_url, "Discogs")


def _download_image(image_url: str, cache_directory: str | Path) -> bytes:
    cache_path = Path(cache_directory) / (
        "artist-" + sha256(image_url.encode("utf-8")).hexdigest() + ".img"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.is_file():
        try:
            data = cache_path.read_bytes()
            if data:
                return data
        except OSError:
            pass
    try:
        request = Request(image_url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=15) as response:
            data = response.read()
    except (HTTPError, URLError, TimeoutError, OSError):
        return b""
    if not data:
        return b""
    try:
        cache_path.write_bytes(data)
    except OSError:
        pass
    return data


def _is_discogs_image_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "i.discogs.com" or host.endswith(".discogs.com")
    )


def extract_artist_hero_url(page: str) -> str:
    candidates = re.findall(
        r"--background-image\s*:\s*url\(([^)]+)\)",
        str(page or ""),
        flags=re.IGNORECASE,
    )
    for raw_url in candidates:
        url = raw_url.strip().strip("\"'")
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme == "https"
            and (host == "mzstatic.com" or host.endswith(".mzstatic.com"))
            and "/video" not in parsed.path.casefold()
            and "previewimage" not in parsed.path.casefold()
            and re.search(r"/\d{3,4}x\d{3,4}[^/]*\.(?:webp|jpg|png)$", parsed.path, re.I)
        ):
            return url
    return ""


def _search_artist_url(artist: str, country: str, app_language: str) -> str:
    wanted = _key(artist)
    if not wanted:
        return ""
    params = {
        "term": artist,
        "country": str(country or "DE").upper(),
        "media": "music",
        "entity": "musicArtist",
        "attribute": "artistTerm",
        "limit": 25,
        "lang": "de_de" if information_language(app_language) == "de" else "en_us",
        "version": 2,
    }
    request = Request(
        f"{SEARCH_ENDPOINT}?{urlencode(params)}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return ""
    exact = [
        item
        for item in payload.get("results", [])
        if isinstance(item, dict) and _key(item.get("artistName", "")) == wanted
    ]
    for item in exact:
        url = str(item.get("artistLinkUrl") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname == "music.apple.com":
            return parsed._replace(query="", fragment="").geturl()
    return ""


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    return re.sub(r"[^a-z0-9]+", "", "".join(
        char for char in normalized if not unicodedata.combining(char)
    ))
