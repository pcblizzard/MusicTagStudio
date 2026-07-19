from __future__ import annotations

import json
import math
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
        values = {
            "Titel": str(track_name or "").strip(),
            "Künstler": str(artist_name or "").strip(),
            "Album": str(album_name or "").strip(),
        }
        missing = [label for label, value in values.items() if not value]
        if missing:
            raise ValueError(
                "Für LRCLIB fehlen: " + ", ".join(missing) + "."
            )
        try:
            duration_value = float(duration)
        except (TypeError, ValueError) as error:
            raise ValueError("Die Titeldauer für LRCLIB ist ungültig.") from error
        if not math.isfinite(duration_value) or duration_value <= 0:
            raise ValueError("Die Titeldauer für LRCLIB muss größer als 0 sein.")
        endpoint = "/api/get-cached" if cached_only else "/api/get"
        query = urlencode(
            {
                "track_name": values["Titel"],
                "artist_name": values["Künstler"],
                "album_name": values["Album"],
                "duration": round(duration_value, 3),
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
    if not isinstance(payload, dict):
        raise LrclibError("LRCLIB lieferte kein gültiges Lyrics-Objekt.")
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
    result = replace(
        document,
        instrumental=bool(payload.get("instrumental", False)),
        provider_id=str(payload.get("id") or ""),
        fetched_at=LyricsDocument.now_iso(),
        metadata={
            **document.metadata,
            "ti": str(payload.get("trackName") or ""),
            "ar": str(payload.get("artistName") or ""),
            "al": str(payload.get("albumName") or ""),
        },
    )
    if result.is_empty:
        raise LyricsNotFound("LRCLIB lieferte keinen Liedtext.")
    return result
