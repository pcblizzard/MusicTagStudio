from __future__ import annotations

from collections import Counter
from statistics import mean

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
            if (
                dominant_signature is not None
                and result.technical_signature
                != dominant_signature
            )
        ]
        elevated = [
            result.path
            for result in valid_results
            if result.peak_status == "elevated"
        ]
        over_zero = [
            result.path
            for result in valid_results
            if result.peak_status == "over_zero"
        ]
        critical = [
            result.path
            for result in valid_results
            if result.peak_status == "critical"
        ]

        bitrate_values = [
            result.bitrate
            for result in valid_results
            if result.bitrate > 0
        ]
        lufs_values = [
            result.integrated_lufs
            for result in valid_results
            if result.integrated_lufs is not None
        ]
        album_gains = [
            result.replaygain_album_gain_db
            for result in valid_results
            if result.replaygain_album_gain_db
            is not None
        ]
        album_peaks = [
            result.replaygain_album_peak
            for result in valid_results
            if result.replaygain_album_peak
            is not None
        ]

        health_score = calculate_health_score(
            technical_outliers=len(outliers),
            elevated_peaks=len(elevated),
            over_zero_peaks=len(over_zero),
            critical_peaks=len(critical),
            missing_files=len(missing),
        )

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
                average_bitrate=(
                    mean(bitrate_values)
                    if bitrate_values
                    else None
                ),
                average_lufs=(
                    mean(lufs_values)
                    if lufs_values
                    else None
                ),
                album_gain_db=(
                    album_gains[0]
                    if album_gains
                    else None
                ),
                album_peak=(
                    album_peaks[0]
                    if album_peaks
                    else None
                ),
                technical_outliers=tuple(
                    outliers
                ),
                elevated_peak_files=tuple(
                    elevated
                ),
                over_zero_peak_files=tuple(
                    over_zero
                ),
                critical_peak_files=tuple(
                    critical
                ),
                missing_analysis_files=tuple(
                    missing
                ),
                health_score=health_score,
            )
        )

    return sorted(
        summaries,
        key=lambda summary:
        summary.display_name.casefold(),
    )


def calculate_health_score(
    *,
    technical_outliers: int,
    elevated_peaks: int,
    over_zero_peaks: int,
    critical_peaks: int,
    missing_files: int,
) -> int:
    score = 100
    score -= min(
        30,
        technical_outliers * 8,
    )
    score -= min(
        10,
        elevated_peaks,
    )
    score -= min(
        25,
        over_zero_peaks * 2,
    )
    score -= min(
        35,
        critical_peaks * 6,
    )
    score -= min(
        30,
        missing_files * 5,
    )

    return max(
        0,
        score,
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
