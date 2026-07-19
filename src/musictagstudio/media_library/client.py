from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..diagnostics import project_root
from ..musicbrainz_http import (
    MUSICBRAINZ_BASE_URL,
    MUSICBRAINZ_USER_AGENT,
    wait_for_musicbrainz_slot,
)


BASE_URL = MUSICBRAINZ_BASE_URL
USER_AGENT = MUSICBRAINZ_USER_AGENT
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60


class MusicBrainzClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class RequestTrace:
    url: str
    status: str
    elapsed_ms: int
    from_cache: bool = False
    result_count: int | None = None
    message: str = ""

    def as_text(self) -> str:
        source = "Cache" if self.from_cache else "Netzwerk"
        count = (
            ""
            if self.result_count is None
            else f" · Ergebnisse: {self.result_count}"
        )
        message = (
            ""
            if not self.message
            else f" · {self.message}"
        )
        return (
            f"{source} · {self.status} · "
            f"{self.elapsed_ms} ms{count}{message}\n"
            f"{self.url}"
        )


class MusicBrainzClient:
    def __init__(
        self,
        *,
        cache_directory: str | Path | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self.cache_directory = Path(
            cache_directory
            or (
                project_root()
                / "cache"
                / "media_library"
                / "musicbrainz"
            )
        )
        self.cache_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.timeout_seconds = max(
            3,
            int(timeout_seconds),
        )
        self.cache_ttl_seconds = max(
            0,
            int(cache_ttl_seconds),
        )
        self.debug_log = (
            project_root()
            / "logs"
            / "musicbrainz.log"
        )
        self.debug_log.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def get_json(
        self,
        endpoint: str,
        params: dict[str, object] | None = None,
        *,
        result_key: str = "",
        use_cache: bool = True,
    ) -> tuple[dict, RequestTrace]:
        endpoint = endpoint.strip("/")
        query = {
            key: value
            for key, value in (params or {}).items()
            if value not in {None, ""}
        }
        query.setdefault(
            "fmt",
            "json",
        )
        url = (
            f"{BASE_URL}/{endpoint}"
            f"?{urlencode(query, doseq=True)}"
        )
        cache_path = self._cache_path(
            url
        )

        if use_cache:
            cached = self._read_cache(
                cache_path
            )
            if cached is not None:
                count = self._result_count(
                    cached,
                    result_key,
                )
                trace = RequestTrace(
                    url=url,
                    status="200 OK",
                    elapsed_ms=0,
                    from_cache=True,
                    result_count=count,
                )
                self._write_trace(
                    trace
                )
                return cached, trace

        started = time.monotonic()
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Accept-Language": "de,en;q=0.8",
                "Cache-Control": "no-cache",
                "Connection": "close",
            },
            method="GET",
        )

        try:
            wait_for_musicbrainz_slot()
            context = ssl.create_default_context()
            with urlopen(
                request,
                timeout=self.timeout_seconds,
                context=context,
            ) as response:
                raw = response.read()
                status_code = int(
                    getattr(
                        response,
                        "status",
                        200,
                    )
                )

            payload = json.loads(
                raw.decode(
                    "utf-8-sig"
                )
            )
            if not isinstance(
                payload,
                dict,
            ):
                raise MusicBrainzClientError(
                    "MusicBrainz lieferte keine JSON-Struktur."
                )

            self._write_cache(
                cache_path,
                payload,
            )
            elapsed = round(
                (
                    time.monotonic()
                    - started
                )
                * 1000
            )
            count = self._result_count(
                payload,
                result_key,
            )
            trace = RequestTrace(
                url=url,
                status=f"{status_code} OK",
                elapsed_ms=elapsed,
                result_count=count,
            )
            self._write_trace(
                trace
            )
            return payload, trace

        except HTTPError as error:
            elapsed = round(
                (
                    time.monotonic()
                    - started
                )
                * 1000
            )
            message = self._http_error_message(
                error
            )
            trace = RequestTrace(
                url=url,
                status=f"HTTP {error.code}",
                elapsed_ms=elapsed,
                message=message,
            )
            self._write_trace(
                trace
            )
            raise MusicBrainzClientError(
                message
            ) from error
        except (
            URLError,
            TimeoutError,
            socket.timeout,
            ssl.SSLError,
        ) as error:
            elapsed = round(
                (
                    time.monotonic()
                    - started
                )
                * 1000
            )
            reason = getattr(
                error,
                "reason",
                error,
            )
            message = (
                "Keine Verbindung zu MusicBrainz: "
                f"{reason}"
            )
            trace = RequestTrace(
                url=url,
                status="Verbindungsfehler",
                elapsed_ms=elapsed,
                message=str(
                    reason
                ),
            )
            self._write_trace(
                trace
            )
            raise MusicBrainzClientError(
                message
            ) from error
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as error:
            elapsed = round(
                (
                    time.monotonic()
                    - started
                )
                * 1000
            )
            message = (
                "Die MusicBrainz-Antwort war kein "
                "gültiges JSON-Dokument."
            )
            trace = RequestTrace(
                url=url,
                status="Ungültige Antwort",
                elapsed_ms=elapsed,
                message=message,
            )
            self._write_trace(
                trace
            )
            raise MusicBrainzClientError(
                message
            ) from error
    def clear_cache(
        self,
    ) -> int:
        removed = 0
        for path in self.cache_directory.glob(
            "*.json"
        ):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    def _cache_path(
        self,
        url: str,
    ) -> Path:
        digest = sha256(
            url.encode(
                "utf-8"
            )
        ).hexdigest()
        return (
            self.cache_directory
            / f"{digest}.json"
        )

    def _read_cache(
        self,
        path: Path,
    ) -> dict | None:
        if (
            not path.is_file()
            or self.cache_ttl_seconds <= 0
        ):
            return None

        age = (
            time.time()
            - path.stat().st_mtime
        )
        if age > self.cache_ttl_seconds:
            return None

        try:
            payload = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return None

        return (
            payload
            if isinstance(
                payload,
                dict,
            )
            else None
        )

    @staticmethod
    def _write_cache(
        path: Path,
        payload: dict,
    ) -> None:
        try:
            path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    @staticmethod
    def _result_count(
        payload: dict,
        result_key: str,
    ) -> int | None:
        if not result_key:
            return None
        value = payload.get(
            result_key
        )
        return (
            len(value)
            if isinstance(
                value,
                list,
            )
            else None
        )

    @staticmethod
    def _http_error_message(
        error: HTTPError,
    ) -> str:
        if error.code == 503:
            return (
                "MusicBrainz ist vorübergehend ausgelastet. "
                "Bitte die Suche in einigen Sekunden wiederholen."
            )
        if error.code == 429:
            return (
                "MusicBrainz hat zu viele Anfragen abgelehnt. "
                "Bitte kurz warten und erneut suchen."
            )
        return (
            "MusicBrainz antwortete mit "
            f"HTTP-Fehler {error.code}."
        )

    def _write_trace(
        self,
        trace: RequestTrace,
    ) -> None:
        timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        line = (
            f"{timestamp} | "
            f"{trace.as_text().replace(chr(10), ' | ')}\n"
        )
        try:
            with self.debug_log.open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(
                    line
                )
        except OSError:
            pass


default_client = MusicBrainzClient()
