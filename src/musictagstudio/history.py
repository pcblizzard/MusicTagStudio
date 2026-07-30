from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import shutil
import uuid


# Es werden nur die letzten N Vorgänge behalten; ältere räumt der Verlauf
# automatisch auf, damit der Ordner nicht unbegrenzt wächst.
DEFAULT_MAX_ENTRIES = 50


# Nur die Tag-Felder – Pfad und Cover werden separat behandelt.
_TAG_FIELDS: tuple[str, ...] = (
    "title",
    "artist",
    "album_artist",
    "album",
    "genre",
    "year",
    "track",
    "total_tracks",
    "disc",
    "total_discs",
    "isrc",
    "label",
    "copyright",
    "composer",
    "comment",
)

# (Tags als dict, Cover-Bytes oder None)
ReadState = Callable[[str], "tuple[dict[str, str], bytes | None]"]
WriteState = Callable[[str, "dict[str, str]", "bytes | None"], None]


@dataclass(frozen=True)
class HistoryEntry:
    entry_id: str
    description: str
    created_at: str
    files: tuple[str, ...]
    committed: bool = False
    # Datei-Umbenennungen (alt, neu). Leer bei reinen Tag-/Cover-Vorgängen.
    # Ein Eintrag hat entweder Tag-Snapshots ODER Moves, nie beides.
    moves: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class FileChanges:
    """Was sich an einer Datei geändert hat – für den Report/Diff."""
    path: str
    field_changes: tuple[tuple[str, str, str], ...] = ()  # (Feld, alt, neu)
    cover_changed: bool = False
    rename: tuple[str, str] | None = None  # (alt, neu)


class HistoryManager:
    """Undo/Redo mit schlanken Tag-/Cover-Schnappschüssen.

    Früher wurden bei jedem Vorgang die kompletten Audiodateien nach
    ``before/``/``after/`` kopiert – bei großen (verlustfreien) Dateien
    summierte sich das auf viele Gigabyte. Ein Tag- oder Cover-Vorgang ändert
    aber nur einen winzigen Teil der Datei. Deshalb wird jetzt pro Datei nur
    der Zustand *Tags + Cover* gesichert (Cover dedupliziert als Blob) und beim
    Rückgängigmachen zurückgeschrieben.
    """

    def __init__(
        self,
        project_root: str | Path,
        *,
        read_state: ReadState | None = None,
        write_state: WriteState | None = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self.root = Path(project_root) / ".musictagstudio" / "history"
        self.root.mkdir(parents=True, exist_ok=True)
        self._blobs = self.root / "blobs"
        self._read_state = read_state or _default_read_state
        self._write_state = write_state or _default_write_state
        self.max_entries = max(1, int(max_entries))
        self.undo_stack: list[HistoryEntry] = []
        self.redo_stack: list[HistoryEntry] = []
        # Vorgänge früherer Sitzungen von der Platte laden, damit Undo auch nach
        # einem Neustart funktioniert, DANN aufräumen (geladene bleiben aktiv).
        self.load_persisted()
        self._prune()

    def load_persisted(self) -> None:
        """Baut den Undo-Stack aus den auf der Platte liegenden Manifesten auf.

        So bleiben abgeschlossene Vorgänge über einen Neustart hinweg
        rückgängig machbar (die Vorher-Schnappschüsse liegen ohnehin auf Platte).
        Chronologisch (ältester zuerst), damit die Stack-Reihenfolge stimmt.
        """
        if not self.root.is_dir():
            return
        entries: list[HistoryEntry] = []
        for directory in sorted(
            (p for p in self.root.iterdir() if p.is_dir() and p.name != "blobs"),
            key=lambda p: p.name,
        ):
            manifest = directory / "manifest.json"
            if not manifest.is_file():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not data.get("committed"):
                continue  # abgebrochene/unbestätigte Vorgänge nicht laden
            entries.append(
                HistoryEntry(
                    entry_id=str(data.get("entry_id", directory.name)),
                    description=str(data.get("description", "")),
                    created_at=str(data.get("created_at", "")),
                    files=tuple(data.get("files", [])),
                    committed=True,
                    moves=tuple(tuple(pair) for pair in data.get("moves", [])),
                )
            )
        self.undo_stack = entries

    def describe_changes(self, entry: HistoryEntry) -> list[FileChanges]:
        """Feldgenaue Änderungen eines Vorgangs (vorher→nachher) für den Report."""
        if entry.moves:
            return [
                FileChanges(path=new, rename=(old, new))
                for old, new in entry.moves
            ]

        before = self._read_snapshot_map(entry.entry_id, "before.json")
        after = self._read_snapshot_map(entry.entry_id, "after.json")
        result: list[FileChanges] = []
        for path in entry.files:
            b = before.get(path, {})
            a = after.get(path, {})
            field_changes = tuple(
                (name, str(b.get("tags", {}).get(name, "")),
                 str(a.get("tags", {}).get(name, "")))
                for name in _TAG_FIELDS
                if str(b.get("tags", {}).get(name, ""))
                != str(a.get("tags", {}).get(name, ""))
            )
            cover_changed = bool(a) and b.get("cover") != a.get("cover")
            if field_changes or cover_changed:
                result.append(
                    FileChanges(
                        path=path,
                        field_changes=field_changes,
                        cover_changed=cover_changed,
                    )
                )
        return result

    def _read_snapshot_map(self, entry_id: str, name: str) -> dict[str, dict]:
        path = self.root / entry_id / name
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return {item["path"]: item for item in snapshot if "path" in item}

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def begin(
        self,
        description: str,
        files: list[str] | tuple[str, ...],
    ) -> HistoryEntry:
        existing = tuple(
            str(Path(path).resolve())
            for path in files
            if Path(path).is_file()
        )
        entry_id = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + "-"
            + uuid.uuid4().hex[:8]
        )
        entry_dir = self.root / entry_id
        entry_dir.mkdir(parents=True, exist_ok=True)

        self._write_snapshot(entry_dir / "before.json", existing)

        entry = HistoryEntry(
            entry_id=entry_id,
            description=description,
            created_at=datetime.now().isoformat(timespec="seconds"),
            files=existing,
        )
        self._write_manifest(entry)

        return entry

    def commit(self, entry: HistoryEntry) -> HistoryEntry:
        entry_dir = self.root / entry.entry_id
        self._write_snapshot(entry_dir / "after.json", entry.files)

        committed = replace(entry, committed=True)
        self.undo_stack.append(committed)
        self.redo_stack.clear()
        self._write_manifest(committed)
        self._prune()

        return committed

    def commit_rename(
        self,
        description: str,
        moves: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    ) -> HistoryEntry:
        """Protokolliert bereits ausgeführte Datei-Umbenennungen (alt, neu).

        Die eigentliche Umbenennung führt der Aufrufer aus (er aktualisiert
        dabei Modell/Tabelle); hier wird nur der reversible Vorgang für
        Undo/Redo festgehalten. Beim Undo werden die Moves rückwärts, beim
        Redo vorwärts ausgeführt.
        """
        recorded = tuple((str(old), str(new)) for old, new in moves)
        entry_id = (
            datetime.now().strftime("%Y%m%d-%H%M%S")
            + "-"
            + uuid.uuid4().hex[:8]
        )
        entry = HistoryEntry(
            entry_id=entry_id,
            description=description,
            created_at=datetime.now().isoformat(timespec="seconds"),
            files=tuple(new for _old, new in recorded),
            committed=True,
            moves=recorded,
        )
        self.undo_stack.append(entry)
        self.redo_stack.clear()
        self._write_manifest(entry)
        self._prune()
        return entry

    def rollback_pending(self, entry: HistoryEntry) -> None:
        self._restore(entry, use_after=False)

    def undo(self) -> HistoryEntry | None:
        if not self.undo_stack:
            return None

        entry = self.undo_stack.pop()
        if entry.moves:
            self._apply_moves(entry, reverse=True)
        else:
            self._restore(entry, use_after=False)
        self.redo_stack.append(entry)

        return entry

    def redo(self) -> HistoryEntry | None:
        if not self.redo_stack:
            return None

        entry = self.redo_stack.pop()

        if entry.moves:
            self._apply_moves(entry, reverse=False)
            self.undo_stack.append(entry)
            return entry

        if not (self.root / entry.entry_id / "after.json").is_file():
            return None

        self._restore(entry, use_after=True)
        self.undo_stack.append(entry)

        return entry

    def _apply_moves(self, entry: HistoryEntry, *, reverse: bool) -> None:
        """Führt die Umbenennungen aus (rückwärts beim Undo, vorwärts beim Redo).

        Best effort und robust: fehlt die Quelle oder existiert das Ziel
        bereits, wird der einzelne Move übersprungen, statt den ganzen
        Vorgang abzubrechen. Beim Rückwärtsgang wird die Reihenfolge gedreht.
        """
        pairs = [(new, old) for old, new in entry.moves] if reverse else list(entry.moves)
        if reverse:
            pairs.reverse()
        for source, target in pairs:
            source_path = Path(source)
            target_path = Path(target)
            if not source_path.is_file() or target_path.exists():
                continue
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.rename(target_path)
            except OSError:
                continue

    def entries(self) -> list[HistoryEntry]:
        return list(reversed(self.undo_stack))

    # -- interne Hilfen -----------------------------------------------------

    def _write_snapshot(self, path: Path, files: tuple[str, ...]) -> None:
        snapshot = []

        for file_path in files:
            tags, cover = self._read_state(file_path)
            snapshot.append(
                {
                    "path": file_path,
                    "tags": tags,
                    "cover": self._store_blob(cover) if cover else None,
                }
            )

        path.write_text(
            json.dumps(snapshot, ensure_ascii=False),
            encoding="utf-8",
        )

    def _restore(self, entry: HistoryEntry, *, use_after: bool) -> None:
        name = "after.json" if use_after else "before.json"
        path = self.root / entry.entry_id / name

        if not path.is_file():
            return

        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        for item in snapshot:
            cover_hash = item.get("cover")
            cover = self._load_blob(cover_hash) if cover_hash else None
            self._write_state(item["path"], item.get("tags", {}), cover)

    def _prune(self) -> None:
        """Behält die neuesten ``max_entries`` Vorgänge, löscht ältere.

        In der aktuellen Sitzung noch benötigte Einträge (im Undo-/Redo-Stack)
        werden nie entfernt; anschließend werden nicht mehr referenzierte
        Cover-Blobs aufgeräumt.
        """
        if not self.root.is_dir():
            return

        active = {entry.entry_id for entry in self.undo_stack}
        active |= {entry.entry_id for entry in self.redo_stack}

        entry_dirs = sorted(
            (
                path
                for path in self.root.iterdir()
                if path.is_dir() and path.name != "blobs"
            ),
            key=lambda path: path.name,  # Zeitstempel-Präfix -> chronologisch
        )
        keep = {path.name for path in entry_dirs[-self.max_entries:]}

        for path in entry_dirs:
            if path.name in keep or path.name in active:
                continue
            shutil.rmtree(path, ignore_errors=True)

        self._collect_blobs()

    def _collect_blobs(self) -> None:
        if not self._blobs.is_dir():
            return

        referenced: set[str] = set()

        for path in self.root.iterdir():
            if not path.is_dir() or path.name == "blobs":
                continue
            for name in ("before.json", "after.json"):
                snapshot_path = path / name
                if not snapshot_path.is_file():
                    continue
                try:
                    snapshot = json.loads(
                        snapshot_path.read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError):
                    continue
                for item in snapshot:
                    digest = item.get("cover")
                    if digest:
                        referenced.add(digest)

        for blob in self._blobs.iterdir():
            if blob.is_file() and blob.name not in referenced:
                blob.unlink(missing_ok=True)

    def _store_blob(self, data: bytes) -> str:
        digest = sha256(data).hexdigest()
        blob = self._blobs / digest

        if not blob.exists():
            self._blobs.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(data)

        return digest

    def _load_blob(self, digest: str) -> bytes | None:
        blob = self._blobs / digest
        return blob.read_bytes() if blob.is_file() else None

    def _write_manifest(self, entry: HistoryEntry) -> None:
        directory = self.root / entry.entry_id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "manifest.json").write_text(
            json.dumps(
                {
                    "entry_id": entry.entry_id,
                    "description": entry.description,
                    "created_at": entry.created_at,
                    "files": list(entry.files),
                    "committed": entry.committed,
                    "moves": [list(pair) for pair in entry.moves],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def _default_read_state(path: str) -> tuple[dict[str, str], bytes | None]:
    from .services.cover import load_cover
    from .services.metadata_io import read_metadata

    song = read_metadata(path)
    tags = {name: str(getattr(song, name, "") or "") for name in _TAG_FIELDS}

    try:
        cover = load_cover(path)
    except Exception:  # noqa: BLE001 - Cover ist optional
        cover = None

    return tags, cover


def _default_write_state(
    path: str,
    tags: dict[str, str],
    cover: bytes | None,
) -> None:
    from .models.song import Song
    from .services.cover import embed_cover, load_cover, remove_cover
    from .services.metadata_io import save_song_metadata

    song = Song(
        path=path,
        title=tags.get("title", ""),
        artist=tags.get("artist", ""),
        album_artist=tags.get("album_artist", ""),
        album=tags.get("album", ""),
        genre=tags.get("genre", ""),
        year=tags.get("year", ""),
        track=tags.get("track", ""),
        total_tracks=tags.get("total_tracks", ""),
        disc=tags.get("disc", ""),
        total_discs=tags.get("total_discs", ""),
        isrc=tags.get("isrc", ""),
        label=tags.get("label", ""),
        copyright=tags.get("copyright", ""),
        composer=tags.get("composer", ""),
        comment=tags.get("comment", ""),
    )
    save_song_metadata(path, song)

    try:
        current = load_cover(path)
    except Exception:  # noqa: BLE001
        current = None

    # Das Cover wird nur angefasst, wenn es sich tatsächlich unterscheidet –
    # ein reiner Tag-Undo schreibt die (unveränderte) Datei so nicht neu.
    if cover == current:
        return

    if cover:
        embed_cover(path, cover)
    else:
        try:
            remove_cover(path)
        except Exception:  # noqa: BLE001
            pass
