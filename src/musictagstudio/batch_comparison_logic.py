from __future__ import annotations

from dataclasses import dataclass

from .comparison_logic import (
    FieldComparison,
    build_field_comparisons,
)
from .models.metadata import MetadataCandidate
from .models.song import Song


COMMON_FIELDS: tuple[str, ...] = (
    "album",
    "album_artist",
    "genre",
    "year",
    "total_tracks",
    "total_discs",
    "label",
    "copyright",
)

TRACK_FIELDS: tuple[str, ...] = (
    "title",
    "artist",
    "track",
    "disc",
    "isrc",
    "composer",
)


@dataclass(frozen=True)
class BatchSongProposal:
    song_row: int
    song: Song
    candidates: list[MetadataCandidate]
    warnings: list[str]


@dataclass(frozen=True)
class CommonFieldComparison:
    field_name: str
    values: dict[str, str]
    default_source: str
    has_conflict: bool
    is_supplemented: bool
    applies_to_rows: tuple[int, ...]


def build_common_field_comparisons(
    proposals: list[BatchSongProposal],
    *,
    primary_source: str,
    feature_handling: str,
) -> list[CommonFieldComparison]:
    per_song = [
        {
            item.field_name: item
            for item in build_field_comparisons(
                proposal.song,
                proposal.candidates,
                primary_source=primary_source,
                feature_handling=feature_handling,
            )
        }
        for proposal in proposals
    ]

    result: list[CommonFieldComparison] = []

    for field_name in COMMON_FIELDS:
        comparisons = [
            mapping.get(field_name)
            for mapping in per_song
        ]

        available = [
            comparison
            for comparison in comparisons
            if comparison is not None
        ]

        if not available:
            continue

        values: dict[str, str] = {}

        for source_name in (
            "local",
            "apple_music",
            "musicbrainz",
        ):
            source_values = [
                comparison.values.get(
                    source_name,
                    "",
                )
                for comparison in available
            ]

            non_empty = [
                value
                for value in source_values
                if value
            ]

            if not non_empty:
                values[source_name] = ""
            elif all(
                value == non_empty[0]
                for value in non_empty
            ) and len(non_empty) == len(proposals):
                values[source_name] = non_empty[0]
            else:
                values[source_name] = "<verschiedene Werte>"

        default_source = _choose_batch_default_source(
            values,
            primary_source,
        )

        distinct_provider_values = {
            value.casefold()
            for source_name, value in values.items()
            if source_name != "local"
            and value
            and value != "<verschiedene Werte>"
        }

        has_conflict = (
            len(distinct_provider_values) > 1
            or any(
                values.get(source_name)
                == "<verschiedene Werte>"
                for source_name in (
                    "apple_music",
                    "musicbrainz",
                )
            )
        )

        is_supplemented = (
            default_source not in {
                "local",
                primary_source,
            }
            and not _usable(
                values.get(
                    primary_source,
                    "",
                )
            )
        )

        result.append(
            CommonFieldComparison(
                field_name=field_name,
                values=values,
                default_source=default_source,
                has_conflict=has_conflict,
                is_supplemented=is_supplemented,
                applies_to_rows=tuple(
                    proposal.song_row
                    for proposal in proposals
                ),
            )
        )

    return result


def build_track_field_comparisons(
    proposal: BatchSongProposal,
    *,
    primary_source: str,
    feature_handling: str,
) -> list[FieldComparison]:
    all_comparisons = build_field_comparisons(
        proposal.song,
        proposal.candidates,
        primary_source=primary_source,
        feature_handling=feature_handling,
    )

    return [
        comparison
        for comparison in all_comparisons
        if comparison.field_name in TRACK_FIELDS
    ]


def _choose_batch_default_source(
    values: dict[str, str],
    primary_source: str,
) -> str:
    if _usable(values.get(primary_source, "")):
        return primary_source

    for source_name in (
        "apple_music",
        "musicbrainz",
    ):
        if _usable(values.get(source_name, "")):
            return source_name

    return "local"


def _usable(value: str) -> bool:
    return bool(
        value
        and value != "<verschiedene Werte>"
    )
