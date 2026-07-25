from __future__ import annotations

import json
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .. import __version__
from . import http_cache


APPLE_USER_AGENT = f"MusicTagStudio/{__version__}"
REQUEST_INTERVAL_SECONDS = 1.0
MAX_RETRY_AFTER_SECONDS = 30.0

_request_lock = threading.Lock()
_last_request_at = 0.0


class AppleRequestError(RuntimeError):
    pass


def request_json(
    request: Request,
    *,
    timeout: float,
) -> dict:
    """Load Apple/iTunes JSON with application-wide pacing and one 429 retry."""
    cache_key = request.full_url
    cached = http_cache.load(cache_key)
    if cached is not None:
        return cached

    for attempt in range(2):
        _wait_for_request_slot()
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            http_cache.store(cache_key, payload)
            return payload
        except HTTPError as error:
            if error.code == 429 and attempt == 0:
                time.sleep(_retry_after(error))
                continue
            raise AppleRequestError(
                f"Apple returned HTTP {error.code}."
            ) from error
        except URLError as error:
            raise AppleRequestError(
                f"Apple could not be reached: {error.reason}"
            ) from error
        except (TimeoutError, OSError, json.JSONDecodeError) as error:
            raise AppleRequestError(
                "Apple returned an invalid or incomplete response."
            ) from error
    raise AppleRequestError("Apple request failed after retry.")


def request_text(
    request: Request,
    *,
    timeout: float,
) -> str:
    """Load an Apple web page as text with the same pacing and 429 retry.

    Used for the public music.apple.com pages whose embedded JSON covers
    catalog entries the iTunes Search API does not index. The response is
    cached in the shared HTTP cache (wrapped as {"html": ...}) so repeated
    album lookups do not re-fetch the page.
    """
    cache_key = f"html:{request.full_url}"
    cached = http_cache.load(cache_key)
    if cached is not None and isinstance(cached.get("html"), str):
        return cached["html"]

    for attempt in range(2):
        _wait_for_request_slot()
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                text = response.read().decode(charset, errors="replace")
            http_cache.store(cache_key, {"html": text})
            return text
        except HTTPError as error:
            if error.code == 429 and attempt == 0:
                time.sleep(_retry_after(error))
                continue
            raise AppleRequestError(
                f"Apple returned HTTP {error.code}."
            ) from error
        except URLError as error:
            raise AppleRequestError(
                f"Apple could not be reached: {error.reason}"
            ) from error
        except (TimeoutError, OSError) as error:
            raise AppleRequestError(
                "Apple returned an invalid or incomplete response."
            ) from error
    raise AppleRequestError("Apple request failed after retry.")


def _wait_for_request_slot() -> None:
    global _last_request_at
    with _request_lock:
        delay = REQUEST_INTERVAL_SECONDS - (
            time.monotonic() - _last_request_at
        )
        if delay > 0:
            time.sleep(delay)
        _last_request_at = time.monotonic()


def _retry_after(error: HTTPError) -> float:
    headers: Any = error.headers
    raw_value = (
        headers.get("Retry-After", "2")
        if headers is not None
        else "2"
    )
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        value = 2.0
    return max(1.0, min(value, MAX_RETRY_AFTER_SECONDS))
