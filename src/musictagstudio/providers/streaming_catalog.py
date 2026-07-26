from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class CatalogAlbumCandidate:
    provider: str
    external_id: str
    external_url: str
    album: str
    artist: str
    year: str
    track_count: int
    confidence: int
    country: str


_ALBUM_SUFFIX_RE = re.compile(r"[\(\[][^\)\]]*[\)\]]\s*$")


def album_has_suffix(title: str) -> bool:
    """True, wenn der Titel mit einem Klammerzusatz endet (z. B. „(Live …)")."""
    return bool(_ALBUM_SUFFIX_RE.search(str(title or "").strip()))


def core_album_key(title: str) -> str:
    """Normalisierter Titel ohne abschließende Klammerzusätze.

    „Das ist alles … (Live In Berlin)" und „… (Live in Berlin 2022)" ergeben
    denselben Kern-Schlüssel.
    """
    core = str(title or "").strip()
    previous = None
    while core != previous:
        previous = core
        core = _ALBUM_SUFFIX_RE.sub("", core).strip()
    return normalize_catalog_text(core)


def album_confidence(
    *,
    wanted_album: str,
    wanted_artist: str,
    wanted_year: str,
    expected_track_count: int | None,
    album: str,
    artist: str,
    year: str,
    track_count: int,
) -> int:
    wanted_album_key = normalize_catalog_text(wanted_album)
    album_key = normalize_catalog_text(album)
    wanted_artist_key = normalize_catalog_text(wanted_artist)
    artist_key = normalize_catalog_text(artist)
    wanted_core = core_album_key(wanted_album)

    score = 0
    if wanted_album_key and wanted_album_key == album_key:
        score += 65
    elif (
        wanted_core
        and wanted_core == core_album_key(album)
        and album_has_suffix(wanted_album)
        and album_has_suffix(album)
    ):
        # Gleicher Kern-Titel, nur der Zusatz unterscheidet sich (z. B. zwei
        # Varianten desselben Live-Albums). Beide müssen einen Zusatz haben,
        # damit nicht Studio- und Live-Version verwechselt werden.
        score += 50
    elif wanted_album_key and (
        wanted_album_key in album_key or album_key in wanted_album_key
    ):
        score += 38

    if wanted_artist_key and wanted_artist_key == artist_key:
        score += 25
    elif wanted_artist_key and (
        wanted_artist_key in artist_key or artist_key in wanted_artist_key
    ):
        score += 12

    wanted_year = str(wanted_year or "")[:4]
    year = str(year or "")[:4]
    if wanted_year and year and wanted_year == year:
        score += 5

    if (
        expected_track_count is not None
        and track_count > 0
        and expected_track_count == track_count
    ):
        score += 5

    return max(0, min(100, score))


def normalize_catalog_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "", text)


def optional_int(value: object) -> int | None:
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
