from __future__ import annotations

import re
import unicodedata
from dataclasses import replace

from ..models.metadata import MetadataCandidate


_BRACKETED_FEATURE_PATTERN = re.compile(
    r"""\s*[\[(]\s*(?:feat(?:uring)?|ft)\.?\s+(?P<artists>[^\]\)]+?)\s*[\])]""",
    re.IGNORECASE | re.VERBOSE,
)
_PLAIN_FEATURE_PATTERN = re.compile(
    r"""\s+(?:feat(?:uring)?|ft)\.?\s+(?P<artists>.+?)\s*$""",
    re.IGNORECASE | re.VERBOSE,
)
_ARTIST_SEPARATOR_PATTERN = re.compile(
    r"\s*(?:,|;|\+|&|\band\b|\bund\b)\s*",
    re.IGNORECASE,
)

APOSTROPHE_TRANSLATION = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "‛": "'",
        "`": "'",
        "´": "'",
    }
)

GENRE_ALIASES: dict[str, str] = {
    "hip hop": "Hip-Hop",
    "hiphop": "Hip-Hop",
    "hip-hop": "Hip-Hop",
    "rap": "Rap",
    "hip hop/rap": "Hip-Hop, Rap",
    "hip-hop/rap": "Hip-Hop, Rap",
    "hip-hop, rap": "Hip-Hop, Rap",
    "r&b/soul": "R&B, Soul",
    "rnb/soul": "R&B, Soul",
    "rhythm and blues": "R&B",
}


def normalize_text(value: str) -> str:
    value = value.translate(APOSTROPHE_TRANSLATION)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_genre(value: str) -> str:
    value = normalize_text(value)
    if not value:
        return ""

    direct = GENRE_ALIASES.get(value.casefold())
    if direct:
        return direct

    parts = re.split(r"\s*[,;/]\s*", value)
    normalized: list[str] = []
    for part in parts:
        if not part:
            continue
        genre = GENRE_ALIASES.get(part.casefold(), part)
        if genre not in normalized:
            normalized.append(genre)
    return ", ".join(normalized)


def normalize_artist_list(value: str) -> str:
    names = _split_artist_names(normalize_text(value))
    return ", ".join(names)


def move_feature_artists(title: str, artist: str) -> tuple[str, str]:
    cleaned_title = normalize_text(title)
    feature_texts: list[str] = []

    def collect_bracketed(match: re.Match[str]) -> str:
        feature_texts.append(match.group("artists"))
        return " "

    cleaned_title = _BRACKETED_FEATURE_PATTERN.sub(collect_bracketed, cleaned_title)
    plain_match = _PLAIN_FEATURE_PATTERN.search(cleaned_title)
    if plain_match is not None:
        feature_texts.append(plain_match.group("artists"))
        cleaned_title = cleaned_title[: plain_match.start()]

    cleaned_title = _clean_title_spacing(cleaned_title)
    artist_names = _split_artist_names(artist)
    for feature_text in feature_texts:
        for feature_artist in _split_artist_names(feature_text):
            if not _contains_artist(artist_names, feature_artist):
                artist_names.append(feature_artist)

    return cleaned_title, ", ".join(artist_names)


def normalize_candidate(
    candidate: MetadataCandidate,
    feature_handling: str = "artist_only",
) -> MetadataCandidate:
    cleaned_title, expanded_artist = move_feature_artists(
        candidate.title,
        candidate.artist,
    )

    if feature_handling == "title_and_artist":
        title = normalize_text(candidate.title)
        artist = expanded_artist
    elif feature_handling == "source":
        title = normalize_text(candidate.title)
        artist = candidate.artist
    else:
        title = cleaned_title
        artist = expanded_artist

    return replace(
        candidate,
        title=normalize_text(title),
        artist=normalize_artist_list(artist),
        album_artist=normalize_artist_list(candidate.album_artist),
        album=normalize_text(candidate.album),
        genre=normalize_genre(candidate.genre),
        year=normalize_text(candidate.year),
        track=normalize_text(candidate.track),
        total_tracks=normalize_text(candidate.total_tracks),
        disc=normalize_text(candidate.disc),
        total_discs=normalize_text(candidate.total_discs),
        isrc=normalize_text(candidate.isrc).upper(),
        label=normalize_text(candidate.label),
        copyright=normalize_text(candidate.copyright),
        composer=normalize_artist_list(candidate.composer),
    )


def _split_artist_names(value: str) -> list[str]:
    value = normalize_text(value)
    if not value:
        return []
    artists: list[str] = []
    for part in _ARTIST_SEPARATOR_PATTERN.split(value):
        artist = normalize_text(part).strip(" ,;+")
        if artist and not _contains_artist(artists, artist):
            artists.append(artist)
    return artists


def _clean_title_spacing(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+([\]\)])", r"\1", value)
    value = re.sub(r"([\[(])\s+", r"\1", value)
    return value.strip(" -–—")


def _contains_artist(artists: list[str], candidate: str) -> bool:
    key = _artist_key(candidate)
    return any(_artist_key(artist) == key for artist in artists)


def _artist_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", value)
