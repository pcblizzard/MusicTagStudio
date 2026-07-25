"""Apple-Music-Websuche als Fallback für nicht indexierte Alben.

Die iTunes-Such-API (``itunes.apple.com/search``) indexiert nicht jedes
Album – manche Veröffentlichungen sind ausschließlich über ihre Album-ID
per Lookup-API erreichbar, tauchen in der Suche aber nie auf. Die
öffentliche Weboberfläche ``music.apple.com`` deckt dagegen den vollen
Katalog ab: Jede Suchseite liefert ihre Ergebnisse als eingebettetes JSON
im ``<script id="serialized-server-data">``-Block mit.

Dieses Modul lädt diese öffentliche Seite (kein Login, kein Token, keine
DRM-Umgehung – nur öffentlich ausgelieferte Metadaten) und extrahiert die
Album-Kandidaten samt Collection-ID. Mit dieser ID lädt die bestehende
Lookup-Pipeline anschließend die vollständige, verlässliche Trackliste.

Die Technik ist der Mp3Tag-„Web Sources"-Skripten nachempfunden
(``https://music.apple.com/{land}/search?l={sprache}&term=%s``), aber
eigenständig in Python umgesetzt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request

from ..diagnostics import get_diagnostic_logger
from .apple_http import (
    APPLE_USER_AGENT,
    AppleRequestError,
    request_text,
)


# Wird über settings.apply_request_intervals() gesetzt und erlaubt es, die
# Websuche komplett abzuschalten (analog zu apple_http.REQUEST_INTERVAL_SECONDS).
WEB_SEARCH_ENABLED = True

SEARCH_ENDPOINT = "https://music.apple.com/{country}/search"
REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_LANGUAGE = "en"
DEFAULT_LIMIT = 8

_SERIALIZED_RE = re.compile(
    r'<script[^>]*id="serialized-server-data"[^>]*>(.*?)</script>',
    re.DOTALL,
)
_ALBUM_ID_RE = re.compile(r"/album/[^/]*/(\d+)")


@dataclass(frozen=True)
class AppleWebAlbum:
    collection_id: str
    album: str
    artist: str
    track_count: int


def search_albums_web(
    album: str,
    artist: str = "",
    *,
    country: str = "DE",
    language: str = DEFAULT_LANGUAGE,
    limit: int = DEFAULT_LIMIT,
) -> list[AppleWebAlbum]:
    """Sucht Alben über die öffentliche Apple-Music-Weboberfläche."""
    logger = get_diagnostic_logger("apple_music")

    terms = [
        part.strip()
        for part in (artist, album)
        if part.strip()
    ]

    if not terms:
        return []

    query = " ".join(terms)
    url = (
        SEARCH_ENDPOINT.format(country=country.lower())
        + "?"
        + urlencode(
            {
                "l": language,
                "term": query,
            }
        )
    )
    request = Request(
        url,
        headers={
            "User-Agent": APPLE_USER_AGENT,
            "Accept": "text/html",
        },
    )

    try:
        html = request_text(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except AppleRequestError as error:
        logger.warning(
            "Apple-Web-Suche fehlgeschlagen | Store=%s | Suche=%r | %s",
            country.upper(),
            query,
            error,
        )
        return []

    albums = parse_search_albums(html)[:limit]
    logger.info(
        "Apple-Web-Suche | Store=%s | Suche=%r | Alben=%d | %s",
        country.upper(),
        query,
        len(albums),
        ", ".join(
            f"{item.collection_id}:{item.album}" for item in albums[:5]
        )
        or "kein Treffer",
    )

    return albums


def parse_search_albums(html: str) -> list[AppleWebAlbum]:
    """Extrahiert Album-Kandidaten aus dem eingebetteten Suchergebnis-JSON."""
    match = _SERIALIZED_RE.search(html)

    if not match:
        return []

    try:
        root = json.loads(match.group(1))
    except (json.JSONDecodeError, TypeError):
        return []

    # Dieselbe ID kann in mehreren Sektionen auftauchen (Top-Treffer ohne
    # Trackzahl, Album-Sektion mit Trackzahl). Reihenfolge des ersten
    # Auftretens bleibt erhalten, fehlende Felder werden nachgetragen.
    ordered_ids: list[str] = []
    merged: dict[str, AppleWebAlbum] = {}

    for section in _iter_sections(root):
        for item in section.get("items", []) or []:
            album = _album_from_item(item)

            if album is None:
                continue

            existing = merged.get(album.collection_id)

            if existing is None:
                ordered_ids.append(album.collection_id)
                merged[album.collection_id] = album
            else:
                merged[album.collection_id] = _merge_album(existing, album)

    return [merged[collection_id] for collection_id in ordered_ids]


def _merge_album(
    first: AppleWebAlbum,
    second: AppleWebAlbum,
) -> AppleWebAlbum:
    return AppleWebAlbum(
        collection_id=first.collection_id,
        album=first.album or second.album,
        artist=first.artist or second.artist,
        track_count=first.track_count or second.track_count,
    )


def _iter_sections(node: object) -> list[dict]:
    """Findet rekursiv die erste ``sections``-Liste im JSON.

    Der genaue Pfad (``data[0].data.sections``) kann sich mit Apples
    Frontend ändern; die rekursive Suche bleibt gegenüber Umbauten robust.
    """
    if isinstance(node, dict):
        sections = node.get("sections")

        if isinstance(sections, list) and all(
            isinstance(entry, dict) for entry in sections
        ):
            return sections

        for value in node.values():
            found = _iter_sections(value)

            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _iter_sections(value)

            if found:
                return found

    return []


def _album_from_item(item: object) -> AppleWebAlbum | None:
    if not isinstance(item, dict):
        return None

    descriptor = item.get("contentDescriptor")

    if not isinstance(descriptor, dict) or descriptor.get("kind") != "album":
        return None

    url = str(descriptor.get("url") or "")
    match = _ALBUM_ID_RE.search(url)

    if match is None:
        return None

    album = _first_link_title(item.get("titleLinks")) or str(
        item.get("title") or ""
    )
    artist = _first_link_title(item.get("subtitleLinks")) or _plain_subtitle(
        item.get("subtitle")
    )

    return AppleWebAlbum(
        collection_id=match.group(1),
        album=album.strip(),
        artist=artist.strip(),
        track_count=_optional_int(item.get("trackCount")) or 0,
    )


def _first_link_title(links: object) -> str:
    if isinstance(links, list):
        for entry in links:
            if isinstance(entry, dict):
                title = str(entry.get("title") or "").strip()

                if title:
                    return title

    return ""


def _plain_subtitle(value: object) -> str:
    """Extrahiert den Künstlernamen aus einem Untertitel wie 'Song · Danger Dan'."""
    text = str(value or "").strip()

    if not text:
        return ""

    # Apple trennt Typ und Künstler mit einem (schmalen) Mittelpunkt.
    for separator in (" · ", " · ", "·"):
        if separator in text:
            return text.split(separator, 1)[1].strip()

    return text


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None

    return None
