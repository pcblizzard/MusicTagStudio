"""Fehlende Tags exakt über die ISRC nachschlagen und ergänzen.

Die ISRC (International Standard Recording Code) identifiziert eine Aufnahme
eindeutig. Damit lässt sich – anders als bei einer unsicheren Textsuche – ein
punktgenauer Treffer bei den bereits vorhandenen, legitimen Providern erzielen:

- **MusicBrainz** ``/ws/2/isrc/{isrc}``
- **Deezer** ``/track/isrc:{isrc}``

Ergänzt werden **nur leere Felder** des Titels; vorhandene Werte bleiben
unangetastet. Die eigentlichen Lookups sind injizierbar, damit die
Zusammenführungslogik ohne Netzwerk testbar bleibt.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ..models.metadata import MetadataCandidate
from ..models.song import Song

# Felder, die aus einem ISRC-Treffer ergänzt werden dürfen (nur wenn leer).
ENRICH_FIELDS: tuple[str, ...] = (
    "title",
    "artist",
    "album_artist",
    "album",
    "genre",
    "year",
    "label",
    "composer",
)

# Rückgabe eines Lookups: passender Kandidat oder None.
LookupFn = Callable[[str], MetadataCandidate | None]


@dataclass(frozen=True)
class IsrcEnrichResult:
    path: str
    isrc: str
    updates: dict[str, str]
    sources: tuple[str, ...] = ()

    @property
    def has_changes(self) -> bool:
        return bool(self.updates)


def _default_lookups() -> tuple[LookupFn, ...]:
    from ..providers import deezer, musicbrainz

    # Reihenfolge = Priorität: MusicBrainz zuerst, dann Deezer als Ergänzung.
    return (
        musicbrainz.lookup_recording_by_isrc,
        deezer.lookup_track_by_isrc,
    )


def _is_blank(value: str) -> bool:
    return not str(value or "").strip()


def merge_updates(
    song: Song, candidates: Iterable[MetadataCandidate]
) -> dict[str, str]:
    """Sammelt für jedes leere Song-Feld den ersten belegten Kandidatenwert."""
    updates: dict[str, str] = {}
    ordered = list(candidates)
    for field in ENRICH_FIELDS:
        if not _is_blank(getattr(song, field, "")):
            continue  # vorhandenen Wert nie überschreiben
        for candidate in ordered:
            value = str(getattr(candidate, field, "") or "").strip()
            if value:
                updates[field] = value
                break
    return updates


def enrich_song(
    song: Song,
    *,
    lookups: tuple[LookupFn, ...] | None = None,
) -> IsrcEnrichResult:
    """Schlägt die ISRC eines Titels nach und liefert die zu setzenden Felder."""
    isrc = str(song.isrc or "").strip()
    if not isrc:
        return IsrcEnrichResult(song.path, "", {})

    lookups = lookups if lookups is not None else _default_lookups()
    candidates: list[MetadataCandidate] = []
    used: list[str] = []
    for lookup in lookups:
        try:
            candidate = lookup(isrc)
        except Exception:  # noqa: BLE001 - defensiv: ein Provider darf ausfallen
            candidate = None
        if candidate is not None:
            candidates.append(candidate)
            used.append(candidate.source)

    return IsrcEnrichResult(
        song.path, isrc, merge_updates(song, candidates), tuple(used)
    )
