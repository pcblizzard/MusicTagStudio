from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .. import __version__


SEARCH_ENDPOINT = "https://api.deezer.com/search/artist"


@dataclass(frozen=True)
class DeezerArtistSuggestion:
    name: str
    fans: int = 0


def suggest_artists(
    query: str,
    *,
    limit: int = 25,
) -> list[DeezerArtistSuggestion]:
    query = str(query or "").strip()
    if len(query) < 3:
        return []
    url = f"{SEARCH_ENDPOINT}?{urlencode({'q': query, 'limit': limit})}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"MusicTagStudio/{__version__}",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return []
    suggestions = {
        str(item.get("name") or "").strip(): DeezerArtistSuggestion(
            name=str(item.get("name") or "").strip(),
            fans=int(item.get("nb_fan") or 0),
        )
        for item in payload.get("data", [])
        if str(item.get("name") or "").strip()
    }
    return sorted(
        suggestions.values(),
        key=lambda item: (-item.fans, item.name.casefold()),
    )
