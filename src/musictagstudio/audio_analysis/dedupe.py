"""Duplikat-Erkennung mit „bestes Exemplar behalten".

Findet mehrfach vorhandene Titel und empfiehlt anhand der lokalen Qualität
(:mod:`quality`), welche Kopie die beste ist – verlustfrei vor verlustbehaftet,
höhere Bit-Tiefe/Abtastrate/Bitrate zuerst. So lassen sich schlechtere
Dubletten gezielt entfernen.

Bewusst **offline & schnell**: Gruppierung über normalisierte Tags (Künstler +
Titel) mit Dauer-Absicherung, Qualität aus den Datei-Headern (mutagen) – kein
vollständiges Dekodieren. Ein akustischer Abgleich (AcoustID) oder die
Echtheitsanalyse ließen sich später als optionale, gründlichere Stufe ergänzen.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .quality import TrackQuality, probe_quality

# Titel mit Dauerunterschied größer als dies gelten als verschiedene Aufnahmen
# (z. B. Studio- vs. Live-Version).
_DURATION_TOLERANCE_SECONDS = 4.0

_WHITESPACE = re.compile(r"\s+")
# Störendes am Rand: Klammerzusätze wie „(Remastered)“, Feature-Angaben.
_FEAT = re.compile(r"\b(feat|ft)\.?\s.*$", re.IGNORECASE)
_BRACKETS = re.compile(r"[\(\[\{].*?[\)\]\}]")
_NONWORD = re.compile(r"[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class DuplicateTrack:
    path: str
    artist: str
    title: str
    album: str
    duration: float
    quality: TrackQuality

    @property
    def filename(self) -> str:
        return Path(self.path).name


@dataclass(frozen=True)
class DuplicateGroup:
    tracks: tuple[DuplicateTrack, ...]
    keep: DuplicateTrack
    removable: tuple[DuplicateTrack, ...] = field(default_factory=tuple)

    @property
    def size(self) -> int:
        return len(self.tracks)


def normalize(text: str) -> str:
    """Robuster Vergleichsschlüssel: klein, ohne Klammern/Feat./Satzzeichen."""
    value = (text or "").casefold().strip()
    value = _FEAT.sub("", value)
    value = _BRACKETS.sub(" ", value)
    value = _NONWORD.sub(" ", value)
    return _WHITESPACE.sub(" ", value).strip()


def quality_rank(track: DuplicateTrack) -> tuple:
    """Höher = besser. Verlustfrei, dann Bit-Tiefe/Rate/Bitrate, dann Dauer."""
    q = track.quality
    return (
        1 if q.lossless else 0,
        q.bit_depth,
        q.sample_rate,
        q.bitrate,
        track.duration,
    )


def rank_for_keeping(tracks: list[DuplicateTrack]) -> list[DuplicateTrack]:
    """Beste Kopie zuerst. Bei Gleichstand deterministisch nach Pfad."""
    by_path = sorted(tracks, key=lambda t: t.path)  # stabiler Gleichstand
    return sorted(by_path, key=quality_rank, reverse=True)


def _cluster_by_duration(
    tracks: list[DuplicateTrack], tolerance: float
) -> list[list[DuplicateTrack]]:
    """Teilt gleichbenannte Titel nach Dauer (verschiedene Aufnahmen trennen)."""
    with_duration = [t for t in tracks if t.duration > 0]
    without = [t for t in tracks if t.duration <= 0]

    clusters: list[list[DuplicateTrack]] = []
    for track in sorted(with_duration, key=lambda t: t.duration):
        if clusters and track.duration - clusters[-1][-1].duration <= tolerance:
            clusters[-1].append(track)
        else:
            clusters.append([track])

    # Dateien ohne Dauerangabe können nicht getrennt werden -> eigene Gruppe.
    if without:
        clusters.append(without)
    return clusters


def find_duplicate_groups(
    tracks: list[DuplicateTrack],
    *,
    duration_tolerance: float = _DURATION_TOLERANCE_SECONDS,
) -> list[DuplicateGroup]:
    """Gruppiert gleiche Titel und markiert je Gruppe die beste Kopie."""
    by_name: dict[tuple[str, str], list[DuplicateTrack]] = defaultdict(list)
    for track in tracks:
        artist = normalize(track.artist)
        title = normalize(track.title)
        if not artist and not title:
            continue  # ohne Künstler/Titel kein sinnvoller Abgleich
        by_name[(artist, title)].append(track)

    groups: list[DuplicateGroup] = []
    for items in by_name.values():
        if len(items) < 2:
            continue
        for cluster in _cluster_by_duration(items, duration_tolerance):
            if len(cluster) < 2:
                continue
            ranked = rank_for_keeping(cluster)
            groups.append(
                DuplicateGroup(
                    tracks=tuple(ranked),
                    keep=ranked[0],
                    removable=tuple(ranked[1:]),
                )
            )

    # Größte/auffälligste Gruppen zuerst.
    groups.sort(key=lambda g: g.size, reverse=True)
    return groups


def _read_duration(path: str) -> float:
    try:
        from mutagen import File as MutagenFile

        info = getattr(MutagenFile(path), "info", None)
        return float(getattr(info, "length", 0.0) or 0.0)
    except Exception:
        return 0.0


def build_track(
    *, path: str, artist: str, title: str, album: str = ""
) -> DuplicateTrack:
    """Baut einen DuplicateTrack: Qualität (mutagen) + Dauer aus dem Header."""
    return DuplicateTrack(
        path=path,
        artist=artist,
        title=title,
        album=album,
        duration=_read_duration(path),
        quality=probe_quality(path),
    )
