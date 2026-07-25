from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CatalogProviderError(RuntimeError):
    pass


def request_json(request: Request, *, timeout: float = 15) -> dict:
    for attempt in range(2):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
                if not isinstance(payload, dict):
                    raise CatalogProviderError(
                        "Der Anbieter hat keine gültige JSON-Antwort geliefert."
                    )
                return payload
        except HTTPError as error:
            if error.code == 429 and attempt == 0:
                time.sleep(_retry_after(error))
                continue
            detail = _http_error_detail(error)
            raise CatalogProviderError(
                f"Der Anbieter meldet HTTP {error.code}"
                + (f": {detail}" if detail else ".")
            ) from error
        except URLError as error:
            raise CatalogProviderError(
                f"Der Anbieter ist nicht erreichbar: {error.reason}"
            ) from error
        except (TimeoutError, OSError, json.JSONDecodeError) as error:
            raise CatalogProviderError(
                "Die Antwort des Anbieters ist ungültig oder unvollständig."
            ) from error
    raise CatalogProviderError("Die Anfrage ist nach einem erneuten Versuch fehlgeschlagen.")


def _http_error_detail(error: HTTPError) -> str:
    try:
        raw = error.read(16_384).decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except (AttributeError, OSError, UnicodeError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    errors = payload.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        first = errors[0]
        detail = str(first.get("detail") or first.get("code") or "").strip()
        return detail[:240]
    return str(
        payload.get("error_description") or payload.get("error") or ""
    ).strip()[:240]


def _retry_after(error: HTTPError) -> float:
    try:
        value = float(error.headers.get("Retry-After", "2"))
    except (AttributeError, TypeError, ValueError):
        value = 2.0
    return max(1.0, min(value, 30.0))
