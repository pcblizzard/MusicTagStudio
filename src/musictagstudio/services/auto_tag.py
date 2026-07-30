"""Auto-Tagging: viele Titel per Klick automatisch taggen.

Baut auf dem vorhandenen Vorschlags-System auf (:func:`build_batch_proposals`
liefert je Titel eine :class:`ProposalResult` mit bewerteten Kandidaten). Hier
wird pro Titel **automatisch der beste Kandidat gewählt** und nur bei
**ausreichender Konfidenz** angewendet – unsichere Fälle landen in einer
„bitte prüfen"-Liste statt blind getaggt zu werden.

Rein datengetrieben und testbar: die eigentliche Übernahme (mit Verlauf/Undo)
erledigt der Aufrufer über die vorhandenen Schreibpfade.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.metadata import MetadataCandidate
from ..models.song import Song
from .proposal import ProposalResult

# Standard-Mindestkonfidenz (%) für die automatische Übernahme.
DEFAULT_THRESHOLD = 90

# Tag-Felder, die automatisch übernommen werden (Kandidat -> Song).
_APPLY_FIELDS = (
    "title", "artist", "album_artist", "album", "genre", "year", "track",
    "total_tracks", "disc", "total_discs", "isrc", "label", "copyright",
    "composer",
)

# Gründe, warum ein Titel NICHT automatisch getaggt wurde.
REASON_NONE = ""
REASON_NO_MATCH = "no_match"
REASON_LOW_CONFIDENCE = "low_confidence"
REASON_NO_CHANGES = "no_changes"


@dataclass(frozen=True)
class AutoTagDecision:
    song_path: str
    applied: bool
    confidence: int
    source: str
    matched_title: str
    updates: dict[str, str] = field(default_factory=dict)
    reason: str = REASON_NONE


def select_candidate(
    result: ProposalResult, *, primary_source: str
) -> MetadataCandidate | None:
    """Bester Kandidat: höchste Konfidenz, bei Gleichstand die primäre Quelle."""
    candidates = list(result.candidates or [])
    if not candidates:
        return None
    best = max(candidates, key=lambda c: c.confidence)
    # Bei (nahezu) gleicher Konfidenz die bevorzugte Quelle nehmen. Direkt in den
    # Kandidaten suchen (result.sources ist im Batch-Flow nicht immer befüllt).
    primary = next(
        (c for c in candidates if c.source == primary_source), None
    )
    if primary is not None and primary.confidence >= best.confidence:
        return primary
    return best


def candidate_updates(candidate: MetadataCandidate, song: Song) -> dict[str, str]:
    """Nur tatsächlich abweichende, nicht-leere Felder als Änderungen."""
    updates: dict[str, str] = {}
    for name in _APPLY_FIELDS:
        value = str(getattr(candidate, name, "") or "")
        if value and value != str(getattr(song, name, "") or ""):
            updates[name] = value
    return updates


def decide(
    result: ProposalResult,
    song: Song,
    *,
    primary_source: str,
    threshold: int = DEFAULT_THRESHOLD,
) -> AutoTagDecision:
    """Entscheidet für einen Titel: automatisch anwenden oder zur Prüfung."""
    candidate = select_candidate(result, primary_source=primary_source)
    if candidate is None or candidate.confidence <= 0:
        return AutoTagDecision(
            song_path=song.path, applied=False, confidence=0, source="",
            matched_title="", reason=REASON_NO_MATCH,
        )

    updates = candidate_updates(candidate, song)
    matched = candidate.album or candidate.title
    if not updates:
        return AutoTagDecision(
            song_path=song.path, applied=False, confidence=candidate.confidence,
            source=candidate.source, matched_title=matched,
            reason=REASON_NO_CHANGES,
        )
    if candidate.confidence < threshold:
        return AutoTagDecision(
            song_path=song.path, applied=False, confidence=candidate.confidence,
            source=candidate.source, matched_title=matched, updates=updates,
            reason=REASON_LOW_CONFIDENCE,
        )
    return AutoTagDecision(
        song_path=song.path, applied=True, confidence=candidate.confidence,
        source=candidate.source, matched_title=matched, updates=updates,
        reason=REASON_NONE,
    )


def run_auto_tag(
    songs: list[Song],
    results: list[ProposalResult],
    *,
    primary_source: str,
    threshold: int = DEFAULT_THRESHOLD,
) -> list[AutoTagDecision]:
    """Wendet :func:`decide` auf jede (Song, ProposalResult)-Paarung an."""
    return [
        decide(result, song, primary_source=primary_source, threshold=threshold)
        for song, result in zip(songs, results)
    ]


def summarize(decisions: list[AutoTagDecision]) -> tuple[int, int, int]:
    """(automatisch angewendet, zu prüfen, ohne Treffer)."""
    applied = sum(1 for d in decisions if d.applied)
    review = sum(
        1 for d in decisions
        if not d.applied and d.reason == REASON_LOW_CONFIDENCE
    )
    no_match = sum(1 for d in decisions if d.reason == REASON_NO_MATCH)
    return applied, review, no_match
