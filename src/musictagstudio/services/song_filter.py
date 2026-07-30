"""Filtern der geladenen Titel nach Text, Genre und Künstler.

Reine, testbare Logik – die UI blendet anhand von :func:`matches` einzelne
Tabellenzeilen aus. ``distinct_values`` füllt die Auswahlfelder (Genre/Künstler)
mit den tatsächlich vorhandenen Werten.
"""

from __future__ import annotations

from ..models.song import Song

# Felder, die die freie Textsuche durchsucht.
_TEXT_FIELDS = ("title", "artist", "album_artist", "album", "genre")


def _norm(value: str) -> str:
    return str(value or "").casefold().strip()


def matches(
    song: Song,
    *,
    text: str = "",
    genre: str = "",
    artist: str = "",
    bpm: str = "",
    bpm_tolerance: float = 3.0,
) -> bool:
    """Passt der Titel zu allen gesetzten Kriterien (leere werden ignoriert)?"""
    needle = _norm(text)
    if needle and not any(
        needle in _norm(getattr(song, field, "")) for field in _TEXT_FIELDS
    ):
        return False
    if genre and _norm(song.genre) != _norm(genre):
        return False
    if artist:
        wanted = _norm(artist)
        if wanted not in (_norm(song.artist), _norm(song.album_artist)):
            return False
    if str(bpm).strip():
        target = _as_float(bpm)
        value = _as_float(song.bpm)
        if target is None or value is None or abs(value - target) > bpm_tolerance:
            return False
    return True


def _as_float(value: str) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def distinct_values(songs: list[Song], field: str) -> list[str]:
    """Sortierte, eindeutige, nicht-leere Werte eines Feldes (Original-Schreibweise).

    Für ``artist`` werden Künstler UND Album-Künstler berücksichtigt.
    """
    seen: dict[str, str] = {}  # normalisiert -> erste Original-Schreibweise
    fields = ("artist", "album_artist") if field == "artist" else (field,)
    for song in songs:
        for name in fields:
            value = str(getattr(song, name, "") or "").strip()
            key = value.casefold()
            if value and key not in seen:
                seen[key] = value
    return sorted(seen.values(), key=str.casefold)
