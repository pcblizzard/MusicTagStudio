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
    # Optionales Qualitätskennzeichen des Anbieters (z. B. TIDAL "Hi-Res
    # Lossless"). Leer, wenn der Anbieter nichts liefert.
    quality: str = ""


_ALBUM_SUFFIX_RE = re.compile(r"[\(\[][^\)\]]*[\)\]]\s*$")


def album_has_suffix(title: str) -> bool:
    """True, wenn der Titel mit einem Klammerzusatz endet (z. B. „(Live …)")."""
    return bool(_ALBUM_SUFFIX_RE.search(str(title or "").strip()))


def album_core_title(title: str) -> str:
    """Lesbarer Titel ohne abschließende Klammerzusätze (Text bleibt erhalten).

    „Das ist alles … (Live In Berlin)" -> „Das ist alles …". Wird der Titel
    komplett entfernt, bleibt der Originaltitel erhalten.
    """
    core = str(title or "").strip()
    previous = None
    while core != previous:
        previous = core
        core = _ALBUM_SUFFIX_RE.sub("", core).strip()
    return core or str(title or "").strip()


def core_album_key(title: str) -> str:
    """Normalisierter Titel ohne abschließende Klammerzusätze.

    „Das ist alles … (Live In Berlin)" und „… (Live in Berlin 2022)" ergeben
    denselben Kern-Schlüssel.
    """
    return normalize_catalog_text(album_core_title(title))


# Führende Artikel (mehrsprachig), die für den toleranten Abgleich entfallen.
_LEADING_ARTICLES = frozenset(
    {"die", "der", "das", "the", "le", "la", "les", "el", "los", "las"}
)
# Verbreitete Editions-/Varianten-Schlagwörter (auch OHNE Klammern).
_EDITION_WORDS_RE = re.compile(
    r"\b(premium|deluxe|special|limited|expanded|remaster(?:ed)?|bonus|"
    r"edition|version|anniversary)\b"
)
_BRACKET_RE = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")


def loose_album_key(title: str) -> str:
    """Editions-/Artikel-toleranter Album-Schlüssel für den Streaming-Abgleich.

    Entfernt Klammerzusätze, die **nur** Editions-/Varianten-Wörter enthalten
    („(Premium Edition)", „(Remastered)"), verbreitete Editions-Wörter ohne
    Klammern sowie einen führenden Artikel. **Inhaltsbestimmende** Zusätze wie
    „(Live In Berlin)", „(Acoustic)" oder „(Remix)" bleiben erhalten, damit
    Studio-/Live-/Remix-Fassungen NICHT verwechselt werden.

    Dadurch gilt „Die Passion Whisky" als dasselbe Album wie
    „Passion Whisky (Premium Edition)", aber ein Studio-Titel bleibt von seiner
    „(Live …)"-Fassung getrennt. Bewusst großzügiger als :func:`core_album_key`
    (dort müssen beide Seiten einen Zusatz tragen).
    """

    def _clean_bracket(match: re.Match) -> str:
        inner = match.group(0)
        # Nur Editions-Wörter im Zusatz -> Zusatz fällt weg. Bleibt sonstiger
        # Inhalt (z. B. „Live"), bleibt der ganze Zusatz erhalten.
        remainder = _EDITION_WORDS_RE.sub(" ", inner)
        remainder = re.sub(r"[^a-z0-9]+", " ", remainder).strip()
        return " " if not remainder else inner

    text = _BRACKET_RE.sub(_clean_bracket, str(title or "").casefold())
    text = _EDITION_WORDS_RE.sub(" ", text)  # freistehende Editions-Wörter
    words = re.sub(r"[^a-z0-9]+", " ", text).split()
    if len(words) > 1 and words[0] in _LEADING_ARTICLES:
        words = words[1:]
    return normalize_catalog_text(" ".join(words))


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
    wanted_loose = loose_album_key(wanted_album)

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
    elif wanted_loose and wanted_loose == loose_album_key(album):
        # Editions-/Artikel-tolerant: „Die Passion Whisky" ==
        # „Passion Whisky (Premium Edition)". Etwas unter dem Kern-Match, da
        # großzügiger (auch einseitiger Zusatz / führender Artikel zählt).
        score += 48
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
