from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from mutagen.flac import FLAC


@dataclass(frozen=True)
class CoverInfo:
    data: bytes
    mime: str
    width: int
    height: int
    depth: int
    colors: int
    picture_type: int
    md5: str

    @property
    def signature(self) -> tuple[object, ...]:
        """
        Eindeutige Vergleichssignatur für die eingebettete Covergrafik.

        Der MD5-Wert vergleicht die tatsächlichen Bilddaten. Zusätzlich
        werden die von FLAC gespeicherten Bildeigenschaften berücksichtigt.
        """
        return (
            self.md5,
            self.mime.casefold(),
            self.width,
            self.height,
            self.depth,
            self.colors,
            self.picture_type,
        )


def load_cover(filepath: str | Path) -> bytes | None:
    """Lädt die Bilddaten des ersten eingebetteten FLAC-Covers."""
    cover_info = load_cover_info(filepath)

    if cover_info is None:
        return None

    return cover_info.data


def load_cover_info(filepath: str | Path) -> CoverInfo | None:
    """Lädt Bilddaten und technische Eigenschaften des ersten Covers."""
    path = Path(filepath)

    if not path.is_file():
        return None

    audio = FLAC(path)

    if not audio.pictures:
        return None

    picture = audio.pictures[0]
    data = bytes(picture.data)

    return CoverInfo(
        data=data,
        mime=str(picture.mime or ""),
        width=int(picture.width or 0),
        height=int(picture.height or 0),
        depth=int(picture.depth or 0),
        colors=int(picture.colors or 0),
        picture_type=int(picture.type),
        md5=hashlib.md5(
            data,
            usedforsecurity=False,
        ).hexdigest(),
    )


def covers_are_identical(
    covers: list[CoverInfo | None],
) -> bool:
    """
    Prüft, ob alle ausgewählten Dateien dasselbe Cover besitzen.

    Auch der gemeinsame Zustand „alle ohne Cover“ gilt als identisch.
    """
    if not covers:
        return True

    first = covers[0]

    if first is None:
        return all(cover is None for cover in covers)

    return all(
        cover is not None
        and cover.signature == first.signature
        for cover in covers
    )
