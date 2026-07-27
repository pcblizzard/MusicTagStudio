from __future__ import annotations

from pathlib import Path

from musictagstudio.history import HistoryManager


def _manager(tmp_path: Path) -> HistoryManager:
    # read/write_state werden bei Move-Vorgängen nicht benötigt.
    return HistoryManager(tmp_path)


def test_commit_rename_enables_undo_redo(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    manager = _manager(project)

    old = tmp_path / "raw.flac"
    new = tmp_path / "01 - Song.flac"
    old.write_bytes(b"audio")
    old.rename(new)  # Aufrufer benennt um, dann protokollieren

    entry = manager.commit_rename("rename", [(str(old), str(new))])
    assert manager.can_undo and not manager.can_redo
    assert entry.moves == ((str(old), str(new)),)

    # Undo: neu -> alt
    manager.undo()
    assert old.is_file() and not new.exists()
    assert manager.can_redo and not manager.can_undo

    # Redo: alt -> neu
    manager.redo()
    assert new.is_file() and not old.exists()
    assert manager.can_undo and not manager.can_redo


def test_undo_skips_when_target_already_exists(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    manager = _manager(project)

    old = tmp_path / "a.flac"
    new = tmp_path / "b.flac"
    new.write_bytes(b"renamed")
    manager.commit_rename("rename", [(str(old), str(new))])

    # Der alte Pfad wurde zwischenzeitlich neu belegt -> Undo darf ihn nicht
    # überschreiben, sondern überspringt den Move.
    old.write_bytes(b"other")
    manager.undo()
    assert old.read_bytes() == b"other"
    assert new.is_file()


def test_manifest_persists_moves(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    manager = _manager(project)
    entry = manager.commit_rename("rename", [("C:/x/a.flac", "C:/x/b.flac")])

    import json

    manifest = json.loads(
        (manager.root / entry.entry_id / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["moves"] == [["C:/x/a.flac", "C:/x/b.flac"]]


def test_rename_and_tag_entries_share_one_undo_stack(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    recorded: list[str] = []
    manager = HistoryManager(
        project,
        read_state=lambda path: ({"title": "T"}, None),
        write_state=lambda path, tags, cover: recorded.append(path),
    )

    tag_file = tmp_path / "tag.flac"
    tag_file.write_bytes(b"x")
    tag_entry = manager.begin("tag", [str(tag_file)])
    manager.commit(tag_entry)

    old = tmp_path / "r.flac"
    new = tmp_path / "r2.flac"
    old.write_bytes(b"y")
    old.rename(new)
    manager.commit_rename("rename", [(str(old), str(new))])

    # Zuletzt committet wurde die Umbenennung -> zuerst rückgängig.
    undone = manager.undo()
    assert undone is not None and undone.moves
    assert old.is_file() and not new.exists()

    # Danach der Tag-Vorgang (Move-frei -> Tag-Restore-Pfad).
    undone = manager.undo()
    assert undone is not None and not undone.moves
    assert recorded  # write_state wurde für den Tag-Undo aufgerufen
