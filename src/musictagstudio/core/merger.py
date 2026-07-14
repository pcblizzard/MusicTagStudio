from __future__ import annotations

from dataclasses import replace

from ..models.metadata import EDITABLE_FIELDS, MergedMetadata, MetadataCandidate
from ..models.song import Song
from .normalizers import normalize_candidate


APPLE_MASTER_FIELDS = {
    "title",
    "artist",
    "album_artist",
    "album",
    "genre",
    "year",
    "track",
    "total_tracks",
    "disc",
    "total_discs",
}
MUSICBRAINZ_MASTER_FIELDS = {
    "isrc",
    "label",
    "copyright",
    "composer",
}
MIN_CONFIDENCE = 35


def song_values(song: Song) -> dict[str, str]:
    return {name: str(getattr(song, name, "") or "") for name in EDITABLE_FIELDS}


def merge_metadata(
    local_song: Song,
    candidates: list[MetadataCandidate],
    feature_handling: str = "artist_only",
    primary_source: str = "apple_music",
) -> MergedMetadata:
    normalized = [
        normalize_candidate(candidate, feature_handling)
        for candidate in candidates
    ]
    values = song_values(local_song)
    sources = {name: "local" for name in EDITABLE_FIELDS}
    confidence = {name: 100 for name in EDITABLE_FIELDS}

    for field_name in EDITABLE_FIELDS:
        chosen = _choose_candidate(
            field_name,
            normalized,
            primary_source,
        )
        if chosen is None:
            continue
        candidate, value = chosen
        values[field_name] = value
        sources[field_name] = candidate.source
        confidence[field_name] = candidate.confidence

    return MergedMetadata(values=values, sources=sources, confidence=confidence)


def apply_merged_metadata(
    song: Song,
    merged: MergedMetadata,
    selected_fields: set[str],
) -> Song:
    updates = {
        field_name: merged.values[field_name]
        for field_name in selected_fields
        if field_name in merged.values
    }
    return replace(song, **updates)


def _choose_candidate(
    field_name: str,
    candidates: list[MetadataCandidate],
    primary_source: str,
) -> tuple[MetadataCandidate, str] | None:
    eligible = [
        candidate
        for candidate in candidates
        if candidate.confidence >= MIN_CONFIDENCE
        and str(
            getattr(
                candidate,
                field_name,
                "",
            )
            or ""
        ).strip()
    ]

    if not eligible:
        return None

    primary_candidates = [
        candidate
        for candidate in eligible
        if candidate.source == primary_source
    ]

    candidate_pool = (
        primary_candidates
        if primary_candidates
        else eligible
    )

    chosen = max(
        candidate_pool,
        key=lambda candidate: candidate.confidence,
    )

    return (
        chosen,
        str(
            getattr(
                chosen,
                field_name,
            )
        ).strip(),
    )
