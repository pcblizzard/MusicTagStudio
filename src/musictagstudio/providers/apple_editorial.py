from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
import html
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..diagnostics import project_root
from .. import __version__
from .theaudiodb import EditorialInfo, EditorialProviderError, information_language


CACHE_SECONDS = 30 * 24 * 60 * 60
USER_AGENT = f"Mozilla/5.0 (compatible; MusicTagStudio/{__version__})"


class _DescriptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._description_depth = 0
        self._paragraph_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if values.get("data-testid") == "description":
            self._description_depth = 1
            return
        if self._description_depth:
            self._description_depth += 1
            if tag == "p" and values.get("data-testid") == "truncate-text":
                self._paragraph_depth = self._description_depth
            elif tag == "br" and self._paragraph_depth:
                self.parts.append("\n")

    def handle_endtag(self, _tag: str) -> None:
        if not self._description_depth:
            return
        if self._paragraph_depth == self._description_depth:
            self._paragraph_depth = 0
        self._description_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._paragraph_depth and data.strip():
            self.parts.append(data)


def fetch_apple_editorial(
    url: str,
    app_language: str,
) -> EditorialInfo | None:
    if not _is_apple_music_url(url):
        return None
    language = information_language(app_language)
    canonical_url, localized_url = _canonical_album_urls(url, language)
    page = _get_page(localized_url, language)
    # The visible editorial block is tied to the selected catalog resource.
    # JSON-LD remains a fallback because a page may contain other schema
    # objects with generic descriptions before the album/artist object.
    text = (
        _html_description(page)
        or _marker_description(page)
        or _json_ld_description(page)
    )
    if not text:
        return None
    return EditorialInfo(
        text=text,
        source="Apple Music",
        source_url=canonical_url,
        language=language,
    )


def _is_apple_music_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    return parsed.scheme == "https" and parsed.hostname == "music.apple.com"


def _canonical_album_urls(url: str, language: str) -> tuple[str, str]:
    """Drop a selected-song query while retaining the unambiguous album ID."""
    parsed = urlparse(url)
    match = re.search(r"/(\d+)$", parsed.path.rstrip("/"))
    path = parsed.path.rstrip("/")
    if match:
        # Preserve Apple's readable slug. Identity comes from the numeric ID,
        # not from an optional ``?i=<song id>`` parameter.
        path = path[: match.end()]
    canonical = parsed._replace(path=path, query="", fragment="").geturl()
    locale = "de-DE" if language == "de" else "en-GB"
    localized = parsed._replace(
        path=path,
        query=f"l={locale}",
        fragment="",
    ).geturl()
    return canonical, localized


def _html_description(page: str) -> str:
    parser = _DescriptionParser()
    parser.feed(page)
    return _clean(" ".join(parser.parts))


def _marker_description(page: str) -> str:
    """Read Apple's server-rendered editorial HTML marker as a fallback."""
    matches = re.findall(
        r"<!--\s*HTML_TAG_START\s*-->(.*?)"
        r"<!--\s*HTML_TAG_END\s*-->",
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    candidates = []
    for value in matches:
        parser = _TextParser()
        parser.feed(value)
        text = _clean(" ".join(parser.parts))
        if len(text) >= 20 and not _looks_like_json(text):
            candidates.append(text)
    return max(candidates, key=len, default="")


def _looks_like_json(text: str) -> bool:
    """Erkennt versehentlich eingesammelte JSON-/JSON-LD-Blöcke."""
    stripped = text.lstrip()
    return (
        stripped.startswith("{")
        or stripped.startswith("[")
        or "@context" in stripped
        or "schema.org" in stripped
    )


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_data(self, data: str) -> None:
        # Inhalte von <script>/<style> sind kein Editorial-Text (z. B. das
        # eingebettete JSON-LD) und werden übersprungen.
        if self._skip_depth:
            return
        if data.strip():
            self.parts.append(data)

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag == "br" and not self._skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1


def _json_ld_description(page: str) -> str:
    parser = _JsonLdParser()
    parser.feed(page)
    for payload in parser.payloads:
        try:
            value = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            continue
        description = _find_description(value)
        if description:
            return _clean(description)
    return ""


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._active = False
        self.payloads: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        self._active = tag == "script" and values.get("type") == "application/ld+json"

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._active = False

    def handle_data(self, data: str) -> None:
        if self._active:
            self.payloads.append(data)


def _find_description(value) -> str:
    if isinstance(value, dict):
        description = value.get("description")
        if isinstance(description, str) and description.strip():
            return description
        for child in value.values():
            found = _find_description(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_description(child)
            if found:
                return found
    return ""


def _clean(value: str) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _get_page(url: str, language: str) -> str:
    cache_dir = project_root() / "cache" / "media_library" / "editorial"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"apple-{sha256(url.encode('utf-8')).hexdigest()}.html"
    if cache_path.is_file() and time.time() - cache_path.stat().st_mtime < CACHE_SECONDS:
        try:
            return cache_path.read_text(encoding="utf-8")
        except OSError:
            pass
    accept_language = "de-DE,de;q=0.9,en;q=0.7" if language == "de" else "en-GB,en;q=0.9"
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": accept_language,
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            page = response.read().decode("utf-8", errors="replace")
    except HTTPError as error:
        raise EditorialProviderError(
            f"Apple Music returned HTTP {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise EditorialProviderError(
            "Apple Music editorial information could not be loaded."
        ) from error
    try:
        cache_path.write_text(page, encoding="utf-8")
    except OSError:
        pass
    return page
