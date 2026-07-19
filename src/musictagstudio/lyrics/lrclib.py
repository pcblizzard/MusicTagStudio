from __future__ import annotations

import json
from dataclasses import replace
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .. import __version__
from .lrc import parse_lrc
from .models import LyricsDocument


class LrclibError(RuntimeError):
    pass


class LyricsNotFound(LrclibError):
    pass


class LrclibClient:
    def __init__(
        self,
        *,
        base_url: str = "https://lrclib.net",
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(
        self,
        *,
        track_name: str,
        artist_name: str,
        album_name: str,
        duration: int | float,
        cached_only: bool = True,
    ) -> LyricsDocument:
        endpoint = "/api/get-cached" if cached_only else "/api/get"
        query = urlencode(
            {
                "track_name": track_name,
                "artist_name": artist_name,
                "album_name": album_name,
                "duration": round(float(duration), 3),
            }
        )
        payload = self._request_json(f"{endpoint}?{query}")
        return document_from_lrclib(payload)

    def _request_json(self, path: str) -> dict:
        request = Request(
            f"{self.base_url}{path}",
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    f"MusicTagStudio/{__version__} "
                    "(https://github.com/pcblizzard/MusicTagStudio)"
                ),
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 404:
                raise LyricsNotFound("Keine Lyrics bei LRCLIB gefunden.") from error
            raise LrclibError(f"LRCLIB HTTP-Fehler {error.code}.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise LrclibError(f"LRCLIB ist nicht erreichbar: {error}") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LrclibError("LRCLIB lieferte eine ungültige Antwort.") from error


def document_from_lrclib(payload: dict) -> LyricsDocument:
    synced_text = str(payload.get("syncedLyrics") or "")
    plain_text = str(payload.get("plainLyrics") or "")
    if synced_text:
        document = parse_lrc(synced_text, source="LRCLIB")
        if plain_text:
            document = replace(document, plain_text=plain_text.strip())
    else:
        document = LyricsDocument(
            plain_text=plain_text.strip(),
            source="LRCLIB",
        )
    return replace(
        document,
        instrumental=bool(payload.get("instrumental", False)),
        provider_id=str(payload.get("id") or ""),
        metadata={
            **document.metadata,
            "ti": str(payload.get("trackName") or ""),
            "ar": str(payload.get("artistName") or ""),
            "al": str(payload.get("albumName") or ""),
        },
    )
