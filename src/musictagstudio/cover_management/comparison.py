from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .models import CoverCandidate


@dataclass(frozen=True)
class CoverComparison:
    relationship: str
    description: str


def md5_bytes(
    data: bytes,
) -> str:
    return hashlib.md5(
        data,
        usedforsecurity=False,
    ).hexdigest()


def compare_cover_candidates(
    left: CoverCandidate,
    right: CoverCandidate,
) -> CoverComparison:
    if (
        left.md5
        and right.md5
        and left.md5 == right.md5
    ):
        return CoverComparison(
            relationship="identical",
            description="Bildinhalt ist identisch.",
        )

    if (
        left.width
        and left.height
        and right.width
        and right.height
        and left.width == right.width
        and left.height == right.height
    ):
        return CoverComparison(
            relationship="same_dimensions",
            description=(
                "Gleiche Abmessungen, aber unterschiedlicher Bildinhalt."
            ),
        )

    if (
        left.width
        and left.height
        and right.width
        and right.height
    ):
        return CoverComparison(
            relationship="different_dimensions",
            description=(
                "Abmessungen und Bildinhalt unterscheiden sich."
            ),
        )

    return CoverComparison(
        relationship="unknown",
        description=(
            "Ein vollständiger Vergleich ist erst nach dem Laden "
            "beider Originaldateien möglich."
        ),
    )


def quality_score(
    *,
    width: int,
    height: int,
    mime: str,
    file_size: int,
    preferred_source_bonus: int = 0,
) -> int:
    if width <= 0 or height <= 0:
        return preferred_source_bonus

    shortest_edge = min(
        width,
        height,
    )
    resolution_score = min(
        55,
        shortest_edge // 60,
    )
    square_score = (
        20
        if width == height
        else max(
            0,
            20 - int(
                abs(width - height)
                / max(width, height)
                * 100
            ),
        )
    )
    format_score = {
        "image/jpeg": 10,
        "image/png": 10,
        "image/webp": 8,
    }.get(
        mime.casefold(),
        5,
    )
    size_score = min(
        15,
        file_size // 200_000,
    )

    return min(
        100,
        resolution_score
        + square_score
        + format_score
        + size_score
        + preferred_source_bonus,
    )
