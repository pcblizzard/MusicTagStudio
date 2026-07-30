"""Änderungs-Journal für Tagging/Umbenennen – Grundlage für Report & Undo.

Jeder Bearbeitungslauf (z. B. „12 Titel getaggt") wird als :class:`ChangeRun`
mit einzelnen :class:`ChangeEntry` festgehalten:

- ``kind == "tags"``: Tag-Schnappschuss **vorher/nachher** einer Datei. Undo
  schreibt den Vorher-Stand zurück (song-level, wie :func:`save_song_metadata`).
- ``kind == "rename"``: alter/neuer Pfad. Undo benennt zurück.

Das Journal ist reine, testbare Datenhaltung (JSON); die eigentliche
Rückabwicklung erledigt :func:`undo_run` über die vorhandenen Schreibfunktionen.
Undo läuft in **umgekehrter** Reihenfolge, damit ein „erst taggen, dann
umbenennen" korrekt zurückgerollt wird.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Tag-Felder, die im Schnappschuss festgehalten werden (ohne Pfad/Cover).
SNAPSHOT_FIELDS = (
    "title", "artist", "album_artist", "album", "genre", "year", "track",
    "total_tracks", "disc", "total_discs", "isrc", "label", "copyright",
    "composer", "comment",
)

# So viele Läufe werden höchstens aufbewahrt.
MAX_RUNS = 100


@dataclass(frozen=True)
class ChangeEntry:
    kind: str  # "tags" | "rename"
    path: str = ""  # betroffene Datei (bei "tags")
    before: dict | None = None  # Tag-Schnappschuss vorher
    after: dict | None = None  # Tag-Schnappschuss nachher
    old_path: str = ""  # bei "rename"
    new_path: str = ""


@dataclass(frozen=True)
class ChangeRun:
    run_id: str
    timestamp: str
    label: str
    entries: tuple[ChangeEntry, ...] = field(default_factory=tuple)

    @property
    def tag_count(self) -> int:
        return sum(1 for e in self.entries if e.kind == "tags")

    @property
    def rename_count(self) -> int:
        return sum(1 for e in self.entries if e.kind == "rename")


def snapshot(song) -> dict:
    """Extrahiert die Tag-Felder eines Song als schlichtes Dict."""
    return {name: getattr(song, name, "") for name in SNAPSHOT_FIELDS}


def diff_fields(before: dict | None, after: dict | None) -> list[tuple[str, str, str]]:
    """Geänderte Felder als (Feld, alt, neu) – für die Report-Anzeige."""
    before = before or {}
    after = after or {}
    changes = []
    for name in SNAPSHOT_FIELDS:
        old = str(before.get(name, ""))
        new = str(after.get(name, ""))
        if old != new:
            changes.append((name, old, new))
    return changes


class ChangeJournal:
    """Persistiert Änderungsläufe als JSON (neueste zuerst)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, run: ChangeRun) -> None:
        runs = self.runs()
        runs.insert(0, run)
        self._write(runs[:MAX_RUNS])

    def runs(self) -> list[ChangeRun]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        result = []
        for item in data:
            try:
                entries = tuple(
                    ChangeEntry(**entry) for entry in item.get("entries", [])
                )
                result.append(
                    ChangeRun(
                        run_id=str(item["run_id"]),
                        timestamp=str(item.get("timestamp", "")),
                        label=str(item.get("label", "")),
                        entries=entries,
                    )
                )
            except (TypeError, KeyError):
                continue
        return result

    def get(self, run_id: str) -> ChangeRun | None:
        return next((r for r in self.runs() if r.run_id == run_id), None)

    def remove(self, run_id: str) -> None:
        self._write([r for r in self.runs() if r.run_id != run_id])

    def _write(self, runs: list[ChangeRun]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = [
                {
                    "run_id": r.run_id,
                    "timestamp": r.timestamp,
                    "label": r.label,
                    "entries": [asdict(e) for e in r.entries],
                }
                for r in runs
            ]
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass


def undo_run(
    run: ChangeRun,
    *,
    write_tags=None,
    rename=None,
) -> tuple[int, list[str]]:
    """Rollt einen Lauf zurück (umgekehrte Reihenfolge). Gibt (ok, Fehler).

    ``write_tags(path, snapshot_dict)`` schreibt einen Tag-Schnappschuss zurück,
    ``rename(src, dst)`` benennt eine Datei um. Werden Standardimplementierungen
    (mutagen/os) injiziert nicht überschrieben, kommen die echten zum Einsatz.
    """
    if write_tags is None:
        write_tags = _default_write_tags
    if rename is None:
        rename = _default_rename

    ok = 0
    errors: list[str] = []
    for entry in reversed(run.entries):
        try:
            if entry.kind == "rename":
                if entry.new_path and entry.old_path:
                    rename(entry.new_path, entry.old_path)
                    ok += 1
            elif entry.kind == "tags" and entry.before is not None:
                write_tags(entry.path, entry.before)
                ok += 1
        except Exception as error:  # noqa: BLE001
            target = entry.path or entry.new_path
            errors.append(f"{Path(target).name}: {error}")
    return ok, errors


def _default_write_tags(path: str, snapshot_dict: dict) -> None:
    from ..models.song import Song
    from .metadata_io import save_song_metadata

    save_song_metadata(path, Song(path=path, **snapshot_dict))


def _default_rename(src: str, dst: str) -> None:
    Path(src).rename(dst)


def default_journal_path() -> Path:
    from ..diagnostics import user_data_dir

    return Path(user_data_dir()) / "change_journal.json"
