from __future__ import annotations

from dataclasses import dataclass

from ..core.merger import merge_metadata
from ..models.metadata import (
    MergedMetadata,
    MetadataCandidate,
)
from ..models.song import Song
from ..provider_catalog import supported_provider_ids
from ..providers.apple_music import (
    AppleMusicProviderError,
    search_song as search_apple,
)
from ..providers.musicbrainz import (
    MusicBrainzProviderError,
    search_song as search_mb,
)
from ..settings import load_settings


@dataclass
class ProposalResult:
    merged: MergedMetadata
    candidates: list[MetadataCandidate]
    warnings: list[str]


def build_proposal(song: Song) -> ProposalResult:
    settings = load_settings()
    candidates: list[MetadataCandidate] = []
    warnings: list[str] = []

    supported = list(supported_provider_ids())

    if settings.selected_provider in supported:
        supported.remove(
            settings.selected_provider
        )
        provider_order = [
            settings.selected_provider,
            *supported,
        ]
    else:
        provider_order = supported

    if not settings.enrich_missing_fields:
        provider_order = provider_order[:1]

    for provider_id in provider_order:
        if provider_id == "apple_music":
            try:
                results = search_apple(
                    song.title,
                    song.artist,
                    song.album,
                    country=settings.apple_country,
                    limit=15,
                )

                if results:
                    candidates.append(results[0])
            except AppleMusicProviderError as error:
                warnings.append(str(error))

        elif provider_id == "musicbrainz":
            try:
                results = search_mb(
                    song.title,
                    song.artist,
                    song.album,
                    limit=10,
                )

                if results:
                    candidates.append(results[0])
            except MusicBrainzProviderError as error:
                warnings.append(str(error))

    return ProposalResult(
        merged=merge_metadata(
            song,
            candidates,
            feature_handling=(
                settings.feature_handling
            ),
            primary_source=(
                settings.selected_provider
            ),
        ),
        candidates=candidates,
        warnings=warnings,
    )
