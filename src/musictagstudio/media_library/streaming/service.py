from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

from ...diagnostics import get_diagnostic_logger
from ...providers.apple_music import (
    AppleMusicProviderError,
    MINIMUM_ALBUM_CONFIDENCE,
    search_album_variants,
)
from ...providers.oauth_catalog import CatalogProviderError
from ...providers.spotify import search_albums as search_spotify_albums
from ...providers.streaming_catalog import CatalogAlbumCandidate
from ...providers.tidal import search_albums as search_tidal_albums
from ...providers.tidal_auth import tidal_is_connected
from .models import (
    AvailabilityStatus,
    StreamingAvailability,
    streaming_release_key,
)

LOGGER = get_diagnostic_logger("streaming")


@dataclass(frozen=True)
class StreamingCheckReport:
    results: dict[str, StreamingAvailability]
    errors: dict[str, str]


def check_streaming_providers(
    album: str,
    artist: str,
    *,
    expected_track_count: int | None,
    track_titles: tuple[str, ...],
    wanted_year: str,
    country: str,
    tidal_client_id: str = "",
    tidal_client_secret: str = "",
    spotify_client_id: str = "",
    spotify_client_secret: str = "",
) -> StreamingCheckReport:
    release_key = streaming_release_key(artist, album, wanted_year)
    LOGGER.info(
        "Prüfung gestartet | album=%r | artist=%r | year=%r | tracks=%r | country=%s",
        album,
        artist,
        wanted_year,
        expected_track_count,
        country.upper(),
    )
    checks: dict[str, Callable[[], StreamingAvailability]] = {
        "apple_music": lambda: _check_apple(
            album,
            artist,
            expected_track_count=expected_track_count,
            track_titles=track_titles,
            wanted_year=wanted_year,
            country=country,
            release_key=release_key,
        )
    }
    if tidal_client_id and (tidal_client_secret or tidal_is_connected()):
        checks["tidal"] = lambda: _check_catalog(
            "tidal",
            search_tidal_albums(
                album,
                artist,
                client_id=tidal_client_id,
                client_secret=tidal_client_secret,
                country=country,
                expected_track_count=expected_track_count,
                wanted_year=wanted_year,
            ),
            release_key,
            country,
        )
    if spotify_client_id and spotify_client_secret:
        checks["spotify"] = lambda: _check_catalog(
            "spotify",
            search_spotify_albums(
                album,
                artist,
                client_id=spotify_client_id,
                client_secret=spotify_client_secret,
                country=country,
                expected_track_count=expected_track_count,
                wanted_year=wanted_year,
            ),
            release_key,
            country,
        )

    results: dict[str, StreamingAvailability] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(checks)) as executor:
        futures = {
            executor.submit(check): provider for provider, check in checks.items()
        }
        for future in as_completed(futures):
            provider = futures[future]
            try:
                results[provider] = future.result()
                result = results[provider]
                LOGGER.info(
                    "%s abgeschlossen | status=%s | id=%s | "
                    "album=%r | artist=%r | year=%r | tracks=%d | confidence=%d",
                    provider,
                    result.status.value,
                    result.external_id or "-",
                    result.album,
                    result.artist,
                    result.year,
                    result.track_count,
                    result.confidence,
                )
            except (AppleMusicProviderError, CatalogProviderError) as error:
                errors[provider] = str(error)
                LOGGER.warning("%s fehlgeschlagen | %s", provider, error)
            except Exception as error:
                errors[provider] = (
                    "Unerwarteter Fehler bei der Anbieterabfrage. "
                    "Weitere Anbieter wurden trotzdem geprüft."
                )
                LOGGER.exception(
                    "%s unerwartet fehlgeschlagen | %s",
                    provider,
                    error,
                )
    return StreamingCheckReport(results=results, errors=errors)


def _check_apple(
    album: str,
    artist: str,
    *,
    expected_track_count: int | None,
    track_titles: tuple[str, ...],
    wanted_year: str,
    country: str,
    release_key: str,
) -> StreamingAvailability:
    candidates = search_album_variants(
        album,
        artist,
        expected_track_count=expected_track_count,
        track_titles=track_titles,
        wanted_year=wanted_year,
        country=country,
        limit=10,
    )
    candidates = [
        candidate
        for candidate in candidates
        if candidate.confidence >= MINIMUM_ALBUM_CONFIDENCE
    ]
    if not candidates:
        return StreamingAvailability.checked(
            provider="apple_music",
            release_key=release_key,
            status=AvailabilityStatus.NOT_FOUND,
            country=country,
        )
    best = candidates[0]
    return StreamingAvailability.available(
        provider="apple_music",
        release_key=release_key,
        external_id=best.collection_id,
        external_url=f"https://music.apple.com/de/album/id{best.collection_id}",
        album=best.album,
        artist=best.artist,
        year=best.year,
        track_count=best.track_count,
        confidence=best.confidence,
        country=country,
        release_date=best.release_date,
    )


def _check_catalog(
    provider: str,
    candidates: list[CatalogAlbumCandidate],
    release_key: str,
    country: str,
) -> StreamingAvailability:
    LOGGER.debug(
        "%s Kandidaten vor Mindestwertfilter | %s",
        provider,
        [
            {
                "id": candidate.external_id,
                "album": candidate.album,
                "artist": candidate.artist,
                "year": candidate.year,
                "tracks": candidate.track_count,
                "confidence": candidate.confidence,
            }
            for candidate in candidates[:5]
        ],
    )
    candidates = [
        candidate
        for candidate in candidates
        if candidate.confidence >= MINIMUM_ALBUM_CONFIDENCE
    ]
    if not candidates:
        return StreamingAvailability.checked(
            provider=provider,
            release_key=release_key,
            status=AvailabilityStatus.NOT_FOUND,
            country=country,
        )
    best = candidates[0]
    return StreamingAvailability.available(
        provider=provider,
        release_key=release_key,
        external_id=best.external_id,
        external_url=best.external_url,
        album=best.album,
        artist=best.artist,
        year=best.year,
        track_count=best.track_count,
        confidence=best.confidence,
        country=country,
        quality=best.quality,
    )
