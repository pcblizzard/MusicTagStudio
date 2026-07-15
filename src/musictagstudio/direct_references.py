from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


APPLE_HOSTS = {
    "music.apple.com",
    "itunes.apple.com",
}

MUSICBRAINZ_HOSTS = {
    "musicbrainz.org",
    "www.musicbrainz.org",
}

MBID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)


@dataclass(frozen=True)
class DirectAlbumReference:
    provider: str
    reference_id: str
    reference_type: str


class DirectAlbumReferenceError(ValueError):
    """Die eingegebene Anbieter-URL oder ID ist nicht gültig."""


def parse_album_reference(
    value: str,
) -> DirectAlbumReference:
    raw = value.strip()

    if not raw:
        raise DirectAlbumReferenceError(
            "Bitte gib einen Album-/Song-Link oder eine ID ein."
        )

    if raw.isdigit():
        return DirectAlbumReference(
            provider="apple_music",
            reference_id=raw,
            reference_type="album",
        )

    if MBID_PATTERN.fullmatch(raw):
        return DirectAlbumReference(
            provider="musicbrainz",
            reference_id=raw.lower(),
            reference_type="release",
        )

    parsed = urlparse(raw)

    if not parsed.scheme or not parsed.netloc:
        raise DirectAlbumReferenceError(
            "Der Eintrag ist weder eine unterstützte URL "
            "noch eine gültige Anbieter-ID."
        )

    host = parsed.netloc.casefold()
    parts = [
        part
        for part in parsed.path.split("/")
        if part
    ]

    if host in APPLE_HOSTS:
        reference_id = _last_numeric_part(parts)

        if reference_id is None:
            raise DirectAlbumReferenceError(
                "In der Apple-Music-URL wurde keine Album-ID gefunden."
            )

        reference_type = (
            "song"
            if "song" in parts
            else "album"
        )

        return DirectAlbumReference(
            provider="apple_music",
            reference_id=reference_id,
            reference_type=reference_type,
        )

    if host in MUSICBRAINZ_HOSTS:
        for reference_type in (
            "release",
            "release-group",
        ):
            if reference_type in parts:
                index = parts.index(reference_type)

                if index + 1 >= len(parts):
                    break

                reference_id = parts[index + 1]

                if not MBID_PATTERN.fullmatch(reference_id):
                    break

                return DirectAlbumReference(
                    provider="musicbrainz",
                    reference_id=reference_id.lower(),
                    reference_type=reference_type,
                )

        raise DirectAlbumReferenceError(
            "Die MusicBrainz-URL enthält keine gültige "
            "Release- oder Release-Group-ID."
        )

    raise DirectAlbumReferenceError(
        "Der Anbieter der URL wird derzeit nicht unterstützt."
    )


def _last_numeric_part(
    parts: list[str],
) -> str | None:
    for part in reversed(parts):
        match = re.search(r"(\d+)$", part)

        if match:
            return match.group(1)

    return None
