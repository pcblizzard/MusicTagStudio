from __future__ import annotations

from collections import Counter

from .models import (
    AlbumAnalysisSummary,
    AudioAnalysisResult,
)
from ..models.song import Song


def group_results_by_album(
    songs: list[Song],
    results: dict[str, AudioAnalysisResult],
) -> list[AlbumAnalysisSummary]:
    grouped: dict[
        tuple[str, str],
        list[tuple[Song, AudioAnalysisResult | None]],
    ] = {}

    for song in songs:
        key = (
            (
                song.album_artist
                or song.artist
                or "Unbekannter Künstler"
            ),
            (
                song.album
                or "Unbekanntes Album"
            ),
        )
        grouped.setdefault(
            key,
            [],
        ).append(
            (
                song,
                results.get(song.path),
            )
        )

    summaries: list[
        AlbumAnalysisSummary
    ] = []

    for key, entries in grouped.items():
        valid_results = [
            result
            for _, result in entries
            if result is not None
            and not result.error
        ]
        missing = [
            song.path
            for song, result in entries
            if result is None
            or result.error
        ]

        signatures = Counter(
            result.technical_signature
            for result in valid_results
        )
        dominant_signature = (
            signatures.most_common(1)[0][0]
            if signatures
            else None
        )

        outliers = [
            result.path
            for result in valid_results
            if dominant_signature is not None
            and result.technical_signature
            != dominant_signature
        ]
        clipping = [
            result.path
            for result in valid_results
            if result.clipping_warning
        ]

        summaries.append(
            AlbumAnalysisSummary(
                album_key=key,
                display_name=(
                    f"{key[0]} – {key[1]}"
                ),
                track_count=len(entries),
                dominant_signature=(
                    dominant_signature
                ),
                technical_outliers=tuple(
                    outliers
                ),
                clipping_files=tuple(
                    clipping
                ),
                missing_analysis_files=tuple(
                    missing
                ),
            )
        )

    return sorted(
        summaries,
        key=lambda summary:
        summary.display_name.casefold(),
    )


def signature_text(
    signature: tuple[object, ...] | None,
) -> str:
    if signature is None:
        return "Keine vollständige Analyse"

    codec, sample_rate, bit_depth, channels = (
        signature
    )
    parts = [
        str(codec).upper()
        if codec
        else "Codec unbekannt",
    ]

    if sample_rate:
        parts.append(
            f"{float(sample_rate) / 1000:.1f} kHz"
        )

    if bit_depth:
        parts.append(
            f"{bit_depth} Bit"
        )

    if channels:
        parts.append(
            f"{channels} Kanäle"
        )

    return " · ".join(parts)
