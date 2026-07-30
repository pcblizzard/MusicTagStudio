from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from musictagstudio.media_library.service import Edition
from musictagstudio.media_library.streaming.models import (
    AvailabilityStatus,
    StreamingAvailability,
)
from musictagstudio.ui.media_library_widget import build_streaming_editions


def _avail(provider, album, tracks, *, status=AvailabilityStatus.AVAILABLE, quality=""):
    return StreamingAvailability(
        provider=provider,
        release_key="k",
        status=status,
        external_id="1",
        external_url=f"https://{provider}/album/1",
        album=album,
        artist="Silla",
        year="2012",
        track_count=tracks,
        confidence=90,
        country="de",
        quality=quality,
    )


def test_available_streaming_hit_becomes_edition():
    results = {
        "deezer": _avail("deezer", "Passion Whisky (Premium Edition)", 40),
    }
    editions = build_streaming_editions(
        results, [], fallback_title="Die Passion Whisky", digital_label="Digital"
    )
    assert len(editions) == 1
    ed = editions[0]
    assert isinstance(ed, Edition)
    assert ed.source == "deezer"
    assert ed.track_count == 40
    assert ed.external_url == "https://deezer/album/1"
    assert ed.format == "Digital"


def test_quality_used_as_format_and_badge():
    results = {"tidal": _avail("tidal", "X", 12, quality="Hi-Res Lossless")}
    ed = build_streaming_editions(
        results, [], fallback_title="X", digital_label="Digital"
    )[0]
    assert ed.format == "Hi-Res Lossless"
    assert ed.badges == ("Hi-Res Lossless",)


def test_not_found_is_skipped():
    results = {
        "spotify": _avail("spotify", "X", 10, status=AvailabilityStatus.NOT_FOUND)
    }
    assert build_streaming_editions(
        results, [], fallback_title="X", digital_label="Digital"
    ) == []


def test_duplicate_of_base_edition_is_skipped():
    base = [Edition(release_id="mb", title="Die Passion Whisky", track_count=18)]
    results = {"deezer": _avail("deezer", "Passion Whisky (Premium Edition)", 18)}
    # Gleiche Trackzahl + gleicher Kern-Titel -> als Dublette ausgelassen.
    assert build_streaming_editions(
        results, base, fallback_title="Die Passion Whisky", digital_label="Digital"
    ) == []


def test_different_track_count_not_treated_as_duplicate():
    base = [Edition(release_id="mb", title="Die Passion Whisky", track_count=18)]
    results = {"deezer": _avail("deezer", "Passion Whisky (Premium Edition)", 40)}
    editions = build_streaming_editions(
        results, base, fallback_title="Die Passion Whisky", digital_label="Digital"
    )
    assert len(editions) == 1
    assert editions[0].track_count == 40


def test_unknown_provider_ignored():
    results = {"qobuz": _avail("qobuz", "X", 10)}
    assert build_streaming_editions(
        results, [], fallback_title="X", digital_label="Digital"
    ) == []
