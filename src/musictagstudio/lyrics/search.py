from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from ..database import connect_database
from ..models.song import Song
from ..providers.genius import search_songs_by_text
from .cache import LyricsCache
from .embedded import read_embedded_lyrics_variants
from .storage import load_sidecar


@dataclass(frozen=True)
class LyricsSearchResult:
    source: str
    title: str
    artist: str
    album: str = ""
    excerpt: str = ""
    local_path: str = ""
    external_url: str = ""


def search_lyrics(
    text: str,
    *,
    songs: tuple[Song, ...] = (),
    genius_access_token: str = "",
    limit: int = 50,
) -> list[LyricsSearchResult]:
    query = " ".join(str(text or "").split())
    if len(query) < 3:
        raise ValueError("Bitte mindestens drei Zeichen des Liedtexts eingeben.")
    results = search_local_lyrics(query, songs=songs, limit=limit)
    remaining = max(0, limit - len(results))
    if genius_access_token.strip() and remaining:
        for candidate in search_songs_by_text(
            query,
            access_token=genius_access_token,
            limit=min(remaining, 20),
        ):
            results.append(
                LyricsSearchResult(
                    source="Genius",
                    title=candidate.title,
                    artist=candidate.artist,
                    album=candidate.album,
                    external_url=candidate.url,
                )
            )
    return results[:limit]


def search_local_lyrics(
    text: str,
    *,
    songs: tuple[Song, ...] = (),
    limit: int = 50,
) -> list[LyricsSearchResult]:
    normalized_query = _normalize(text)
    if not normalized_query:
        return []
    results: list[LyricsSearchResult] = []
    seen: set[tuple[str, str, str]] = set()
    song_lookup = {
        (
            _normalize(song.title),
            _normalize(song.artist),
            _normalize(song.album),
        ): song
        for song in songs
    }

    cache = LyricsCache()
    with connect_database(cache.path) as connection:
        rows = connection.execute(
            "SELECT cache_key, document_json FROM lyrics_cache"
        ).fetchall()
    for cache_key, document_json in rows:
        try:
            payload = json.loads(document_json)
        except (TypeError, json.JSONDecodeError):
            continue
        lyrics = str(payload.get("plain_text") or "")
        if normalized_query not in _normalize(lyrics):
            continue
        fields = str(cache_key).split("\x1f")
        title, artist, album = (fields + ["", "", ""])[:3]
        key = (title.casefold(), artist.casefold(), album.casefold())
        if key in seen:
            continue
        seen.add(key)
        matching_song = song_lookup.get(
            (_normalize(title), _normalize(artist), _normalize(album))
        )
        results.append(
            LyricsSearchResult(
                source="Lyrics-Cache",
                title=matching_song.title if matching_song else title,
                artist=matching_song.artist if matching_song else artist,
                album=matching_song.album if matching_song else album,
                excerpt=_excerpt(lyrics, text),
                local_path=matching_song.path if matching_song else "",
            )
        )
        if len(results) >= limit:
            return results

    for song in songs:
        path = Path(song.path)
        documents = []
        if path.with_suffix(".lrc").is_file():
            document = load_sidecar(path)
            if document is not None:
                documents.append(document)
        documents.extend(read_embedded_lyrics_variants(path))
        matching_document = next(
            (
                document
                for document in documents
                if normalized_query in _normalize(document.display_text())
            ),
            None,
        )
        if matching_document is None:
            continue
        lyrics = matching_document.display_text()
        key = (
            song.title.casefold(),
            song.artist.casefold(),
            song.album.casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        results.append(
            LyricsSearchResult(
                source=(
                    "Lokale LRC-Datei"
                    if matching_document.source.casefold().startswith("lrc")
                    else "Eingebettete Lyrics"
                ),
                title=song.title,
                artist=song.artist,
                album=song.album,
                excerpt=_excerpt(lyrics, text),
                local_path=song.path,
            )
        )
        if len(results) >= limit:
            break
    return results


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"\w+", str(value or "").casefold()))


def _excerpt(lyrics: str, query: str, radius: int = 70) -> str:
    collapsed = " ".join(str(lyrics or "").split())
    position = collapsed.casefold().find(" ".join(query.casefold().split()))
    if position < 0:
        return collapsed[: radius * 2].strip()
    start = max(0, position - radius)
    end = min(len(collapsed), position + len(query) + radius)
    prefix = "… " if start else ""
    suffix = " …" if end < len(collapsed) else ""
    return f"{prefix}{collapsed[start:end].strip()}{suffix}"
