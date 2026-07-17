from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import shutil
import uuid


@dataclass(frozen=True)
class HistoryEntry:
    entry_id: str
    description: str
    created_at: str
    files: tuple[str, ...]
    before_directory: str
    after_directory: str | None = None


class HistoryManager:
    """Session undo/redo with persistent, full-file safety copies."""

    def __init__(
        self,
        project_root: str | Path,
    ) -> None:
        self.root = (
            Path(project_root)
            / ".musictagstudio"
            / "history"
        )
        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.undo_stack: list[
            HistoryEntry
        ] = []
        self.redo_stack: list[
            HistoryEntry
        ] = []

    @property
    def can_undo(self) -> bool:
        return bool(
            self.undo_stack
        )

    @property
    def can_redo(self) -> bool:
        return bool(
            self.redo_stack
        )

    def begin(
        self,
        description: str,
        files: list[str] | tuple[str, ...],
    ) -> HistoryEntry:
        existing = tuple(
            str(
                Path(path).resolve()
            )
            for path in files
            if Path(path).is_file()
        )
        entry_id = (
            datetime.now().strftime(
                "%Y%m%d-%H%M%S"
            )
            + "-"
            + uuid.uuid4().hex[:8]
        )
        entry_dir = (
            self.root
            / entry_id
        )
        before = (
            entry_dir
            / "before"
        )
        before.mkdir(
            parents=True,
            exist_ok=True,
        )

        for index, path in enumerate(
            existing
        ):
            source = Path(path)
            target = (
                before
                / f"{index:05d}{source.suffix}"
            )
            shutil.copy2(
                source,
                target,
            )

        entry = HistoryEntry(
            entry_id=entry_id,
            description=description,
            created_at=datetime.now().isoformat(
                timespec="seconds"
            ),
            files=existing,
            before_directory=str(
                before
            ),
        )
        self._write_manifest(
            entry
        )

        return entry

    def commit(
        self,
        entry: HistoryEntry,
    ) -> HistoryEntry:
        entry_dir = (
            self.root
            / entry.entry_id
        )
        after = (
            entry_dir
            / "after"
        )
        after.mkdir(
            parents=True,
            exist_ok=True,
        )

        for index, path in enumerate(
            entry.files
        ):
            source = Path(path)

            if source.is_file():
                shutil.copy2(
                    source,
                    after
                    / (
                        f"{index:05d}"
                        f"{source.suffix}"
                    ),
                )

        committed = HistoryEntry(
            entry_id=entry.entry_id,
            description=entry.description,
            created_at=entry.created_at,
            files=entry.files,
            before_directory=(
                entry.before_directory
            ),
            after_directory=str(
                after
            ),
        )
        self.undo_stack.append(
            committed
        )
        self.redo_stack.clear()
        self._write_manifest(
            committed
        )

        return committed

    def rollback_pending(
        self,
        entry: HistoryEntry,
    ) -> None:
        self._restore(
            entry,
            use_after=False,
        )

    def undo(self) -> HistoryEntry | None:
        if not self.undo_stack:
            return None

        entry = self.undo_stack.pop()
        self._restore(
            entry,
            use_after=False,
        )
        self.redo_stack.append(
            entry
        )

        return entry

    def redo(self) -> HistoryEntry | None:
        if not self.redo_stack:
            return None

        entry = self.redo_stack.pop()

        if not entry.after_directory:
            return None

        self._restore(
            entry,
            use_after=True,
        )
        self.undo_stack.append(
            entry
        )

        return entry

    def entries(
        self,
    ) -> list[HistoryEntry]:
        return list(
            reversed(
                self.undo_stack
            )
        )

    def _restore(
        self,
        entry: HistoryEntry,
        *,
        use_after: bool,
    ) -> None:
        directory = Path(
            entry.after_directory
            if use_after
            else entry.before_directory
        )

        for index, target_path in enumerate(
            entry.files
        ):
            target = Path(
                target_path
            )
            source = (
                directory
                / (
                    f"{index:05d}"
                    f"{target.suffix}"
                )
            )

            if source.is_file():
                target.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                shutil.copy2(
                    source,
                    target,
                )

    def _write_manifest(
        self,
        entry: HistoryEntry,
    ) -> None:
        directory = (
            self.root
            / entry.entry_id
        )
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        (
            directory
            / "manifest.json"
        ).write_text(
            json.dumps(
                {
                    "entry_id": (
                        entry.entry_id
                    ),
                    "description": (
                        entry.description
                    ),
                    "created_at": (
                        entry.created_at
                    ),
                    "files": list(
                        entry.files
                    ),
                    "before_directory": (
                        entry.before_directory
                    ),
                    "after_directory": (
                        entry.after_directory
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
