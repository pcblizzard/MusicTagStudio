from __future__ import annotations

import re
import unicodedata


_BRACKETED_FEATURE_PATTERN = re.compile(
    r"""
    \s*
    [\[(]
    \s*
    (?:
        feat(?:uring)?
        |
        ft
    )
    \.?
    \s+
    (?P<artists>[^\]\)]+?)
    \s*
    [\])]
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PLAIN_FEATURE_PATTERN = re.compile(
    r"""
    \s+
    (?:
        feat(?:uring)?
        |
        ft
    )
    \.?
    \s+
    (?P<artists>.+?)
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

_ARTIST_SEPARATOR_PATTERN = re.compile(
    r"\s*(?:,|;|\+|&|\band\b|\bund\b)\s*",
    re.IGNORECASE,
)


def move_feature_artists(
    title: str,
    artist: str,
) -> tuple[str, str]:
    """
    Verschiebt Feature-Nennungen aus dem Titel in das Künstlerfeld.

    Erkannte Beispiele:
    - Titel [feat. Künstler]
    - Titel (feat. Künstler)
    - Titel feat. Künstler
    - Titel [ft Künstler]
    - Titel (featuring Künstler)

    Rückgabe:
    - bereinigter Titel
    - Künstlerliste im MusicTagStudio-Format: "A, B, C"
    """
    cleaned_title = title.strip()
    feature_texts: list[str] = []

    def collect_bracketed(match: re.Match[str]) -> str:
        feature_texts.append(match.group("artists"))
        return " "

    cleaned_title = _BRACKETED_FEATURE_PATTERN.sub(
        collect_bracketed,
        cleaned_title,
    )

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

    normalized_artist = ", ".join(artist_names)

    return cleaned_title, normalized_artist


def _split_artist_names(value: str) -> list[str]:
    value = value.strip()

    if not value:
        return []

    parts = _ARTIST_SEPARATOR_PATTERN.split(value)
    artists: list[str] = []

    for part in parts:
        artist = _clean_artist_name(part)

        if artist and not _contains_artist(artists, artist):
            artists.append(artist)

    return artists


def _clean_artist_name(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ,;+")


def _clean_title_spacing(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+([\]\)])", r"\1", value)
    value = re.sub(r"([\[(])\s+", r"\1", value)
    return value.strip(" -–—")


def _contains_artist(
    artists: list[str],
    candidate: str,
) -> bool:
    candidate_key = _artist_key(candidate)

    return any(
        _artist_key(artist) == candidate_key
        for artist in artists
    )


def _artist_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value
