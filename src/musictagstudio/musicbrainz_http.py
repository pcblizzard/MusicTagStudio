from __future__ import annotations

import threading
import time

from . import __version__


MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2"
MUSICBRAINZ_USER_AGENT = (
    f"MusicTagStudio/{__version__} "
    "(https://github.com/pcblizzard/MusicTagStudio)"
)
MUSICBRAINZ_REQUEST_INTERVAL_SECONDS = 1.05

_request_lock = threading.Lock()
_last_request_started_at = 0.0


def wait_for_musicbrainz_slot() -> None:
    """Reserve one application-wide MusicBrainz request slot."""
    global _last_request_started_at
    with _request_lock:
        delay = MUSICBRAINZ_REQUEST_INTERVAL_SECONDS - (
            time.monotonic() - _last_request_started_at
        )
        if delay > 0:
            time.sleep(delay)
        _last_request_started_at = time.monotonic()
