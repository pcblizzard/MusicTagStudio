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
) -> MergedMetadata:
    normalized = [
        normalize_candidate(candidate, feature_handling)
        for candidate in candidates
    ]
    values = song_values(local_song)
    sources = {name: "local" for name in EDITABLE_FIELDS}
    confidence = {name: 100 for name in EDITABLE_FIELDS}

    for field_name in EDITABLE_FIELDS:
        chosen = _choose_candidate(field_name, normalized)
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
) -> tuple[MetadataCandidate, str] | None:
    eligible = [
        candidate
        for candidate in candidates
        if candidate.confidence >= MIN_CONFIDENCE
        and str(getattr(candidate, field_name, "") or "").strip()
    ]
    if not eligible:
        return None

    def priority(candidate: MetadataCandidate) -> tuple[int, int]:
        if field_name in APPLE_MASTER_FIELDS:
            source_priority = 3 if candidate.source == "apple_music" else 2
        elif field_name in MUSICBRAINZ_MASTER_FIELDS:
            source_priority = 3 if candidate.source == "musicbrainz" else 2
        else:
            source_priority = 1
        return source_priority, candidate.confidence

    chosen = max(eligible, key=priority)
    return chosen, str(getattr(chosen, field_name)).strip()
