from __future__ import annotations

from dataclasses import dataclass
import re

from .cache import LyricsCache, lyrics_cache_key
from .duration import read_duration_seconds
from .embedded import read_embedded_lyrics_variants
from .lrclib import LrclibClient
from .models import LyricsDocument
from .storage import load_sidecar


@dataclass(frozen=True)
class LyricsRequest:
    audio_path: str
    title: str
    artist: str
    album: str
    duration: float = 0.0


@dataclass(frozen=True)
class LyricsResolution:
    selected: LyricsDocument | None
    candidates: tuple[LyricsDocument, ...]
    warning: str = ""


class LyricsResolver:
    def __init__(
        self,
        *,
        cache: LyricsCache | None = None,
        client: LrclibClient | None = None,
    ) -> None:
        self.cache = cache or LyricsCache()
        self.client = client or LrclibClient()

    def local(self, request: LyricsRequest) -> LyricsResolution:
        candidates: list[LyricsDocument] = []
        try:
            sidecar = load_sidecar(request.audio_path)
        except (OSError, UnicodeError):
            sidecar = None
        if sidecar is not None:
            candidates.append(sidecar)
        candidates.extend(read_embedded_lyrics_variants(request.audio_path))
        duration = request.duration or read_duration_seconds(request.audio_path)
        if duration > 0:
            cached = self.cache.get(
                lyrics_cache_key(
                    request.title, request.artist, request.album, duration
                )
            )
            if cached is not None:
                candidates.append(cached)
        selected = candidates[0] if candidates else None
        return LyricsResolution(
            selected=selected,
            candidates=tuple(candidates),
            warning=live_version_warning(request, selected),
        )

    def online(
        self,
        request: LyricsRequest,
        *,
        live: bool = False,
    ) -> LyricsResolution:
        duration = request.duration or read_duration_seconds(request.audio_path)
        document = self.client.get(
            track_name=request.title,
            artist_name=request.artist,
            album_name=request.album,
            duration=duration,
            cached_only=not live,
        )
        key = lyrics_cache_key(
            request.title, request.artist, request.album, duration
        )
        self.cache.put(key, document)
        local = self.local(request)
        candidates = _dedupe_documents((*local.candidates, document))
        return LyricsResolution(
            selected=document,
            candidates=candidates,
            warning=live_version_warning(request, document),
        )


_LIVE_PATTERN = re.compile(
    r"(?:\blive\b|\bconcert\b|\bunplugged\b|\bkonzert\b)",
    flags=re.IGNORECASE,
)


def live_version_warning(
    request: LyricsRequest,
    document: LyricsDocument | None,
) -> str:
    if document is None:
        return ""
    track_is_live = bool(_LIVE_PATTERN.search(f"{request.title} {request.album}"))
    lyric_label = " ".join(
        (
            document.metadata.get("ti", ""),
            document.metadata.get("al", ""),
            document.source,
        )
    )
    lyrics_are_live = bool(_LIVE_PATTERN.search(lyric_label))
    if track_is_live and not lyrics_are_live:
        return (
            "Hinweis: Dies ist eine Live-Version. Der gefundene Text kann von "
            "der tatsächlichen Live-Darbietung abweichen."
        )
    return ""


def _dedupe_documents(
    documents: tuple[LyricsDocument, ...],
) -> tuple[LyricsDocument, ...]:
    result: list[LyricsDocument] = []
    seen: set[tuple] = set()
    for document in documents:
        key = (
            document.source,
            document.provider_id,
            document.plain_text,
            document.synced_lines,
        )
        if key not in seen:
            seen.add(key)
            result.append(document)
    return tuple(result)
