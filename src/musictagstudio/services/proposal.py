from __future__ import annotations

from dataclasses import dataclass

from ..core.merger import merge_metadata
from ..models.metadata import MergedMetadata, MetadataCandidate
from ..models.song import Song
from ..providers.apple_music import AppleMusicProviderError, search_song as search_apple
from ..providers.musicbrainz import MusicBrainzProviderError, search_song as search_mb
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

    if settings.apple_music_enabled:
        try:
            apple = search_apple(
                song.title,
                song.artist,
                song.album,
                country=settings.apple_country,
                limit=15,
            )
            if apple:
                candidates.append(apple[0])
        except AppleMusicProviderError as error:
            warnings.append(str(error))

    if settings.musicbrainz_enabled:
        try:
            musicbrainz = search_mb(
                song.title,
                song.artist,
                song.album,
                limit=10,
            )
            if musicbrainz:
                candidates.append(musicbrainz[0])
        except MusicBrainzProviderError as error:
            warnings.append(str(error))

    return ProposalResult(
        merged=merge_metadata(
            song,
            candidates,
            feature_handling=settings.feature_handling,
        ),
        candidates=candidates,
        warnings=warnings,
    )
