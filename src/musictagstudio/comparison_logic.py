from __future__ import annotations

from dataclasses import dataclass

from .core.normalizers import normalize_candidate
from .models.metadata import (
    EDITABLE_FIELDS,
    MetadataCandidate,
)
from .models.song import Song


SOURCE_ORDER = (
    "local",
    "apple_music",
    "musicbrainz",
)


@dataclass(frozen=True)
class FieldComparison:
    field_name: str
    values: dict[str, str]
    default_source: str
    has_conflict: bool
    is_supplemented: bool


def build_field_comparisons(
    song: Song,
    candidates: list[MetadataCandidate],
    *,
    primary_source: str,
    feature_handling: str,
) -> list[FieldComparison]:
    normalized_candidates = [
        normalize_candidate(
            candidate,
            feature_handling,
        )
        for candidate in candidates
    ]

    by_source = {
        candidate.source: candidate
        for candidate in normalized_candidates
    }

    comparisons: list[FieldComparison] = []

    for field_name in EDITABLE_FIELDS:
        values = {
            "local": str(
                getattr(song, field_name, "")
                or ""
            ).strip(),
        }

        for source_name in SOURCE_ORDER[1:]:
            candidate = by_source.get(source_name)
            values[source_name] = (
                str(
                    getattr(
                        candidate,
                        field_name,
                        "",
                    )
                    or ""
                ).strip()
                if candidate is not None
                else ""
            )

        non_empty_provider_values = {
            value
            for source_name, value in values.items()
            if source_name != "local" and value
        }

        if not non_empty_provider_values:
            continue

        default_source = choose_default_source(
            values,
            primary_source=primary_source,
        )

        distinct_provider_values = {
            value.casefold()
            for source_name, value in values.items()
            if source_name != "local" and value
        }

        has_conflict = (
            len(distinct_provider_values) > 1
        )

        is_supplemented = (
            default_source not in {
                "local",
                primary_source,
            }
            and not values.get(primary_source, "")
        )

        comparisons.append(
            FieldComparison(
                field_name=field_name,
                values=values,
                default_source=default_source,
                has_conflict=has_conflict,
                is_supplemented=is_supplemented,
            )
        )

    return comparisons


def choose_default_source(
    values: dict[str, str],
    *,
    primary_source: str,
) -> str:
    primary_value = values.get(
        primary_source,
        "",
    ).strip()

    if primary_value:
        return primary_source

    for source_name in SOURCE_ORDER[1:]:
        if values.get(source_name, "").strip():
            return source_name

    return "local"
