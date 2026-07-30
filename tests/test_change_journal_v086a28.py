from __future__ import annotations

from pathlib import Path

from musictagstudio.models.song import Song
from musictagstudio.services.change_journal import (
    ChangeEntry,
    ChangeJournal,
    ChangeRun,
    diff_fields,
    snapshot,
    undo_run,
)


def _run(run_id="r1", entries=()):
    return ChangeRun(run_id=run_id, timestamp="2026-07-30T10:00:00", label="Lauf",
                     entries=tuple(entries))


def test_snapshot_and_diff():
    a = snapshot(Song(title="Alt", artist="X"))
    b = snapshot(Song(title="Neu", artist="X"))
    changes = diff_fields(a, b)
    assert changes == [("title", "Alt", "Neu")]


def test_journal_roundtrip(tmp_path: Path):
    j = ChangeJournal(tmp_path / "j.json")
    entry = ChangeEntry(kind="tags", path="a.flac",
                        before={"title": "Alt"}, after={"title": "Neu"})
    j.append(_run("r1", [entry]))
    runs = j.runs()
    assert len(runs) == 1
    assert runs[0].run_id == "r1"
    assert runs[0].entries[0].after == {"title": "Neu"}
    assert runs[0].tag_count == 1


def test_journal_newest_first_and_remove(tmp_path: Path):
    j = ChangeJournal(tmp_path / "j.json")
    j.append(_run("r1"))
    j.append(_run("r2"))
    assert [r.run_id for r in j.runs()] == ["r2", "r1"]
    j.remove("r2")
    assert [r.run_id for r in j.runs()] == ["r1"]


def test_undo_writes_before_snapshot():
    entry = ChangeEntry(kind="tags", path="a.flac",
                        before={"title": "Alt"}, after={"title": "Neu"})
    written = {}
    ok, errors = undo_run(
        _run("r1", [entry]),
        write_tags=lambda path, snap: written.update({path: snap}),
        rename=lambda s, d: None,
    )
    assert ok == 1 and not errors
    assert written == {"a.flac": {"title": "Alt"}}


def test_undo_reverses_rename_then_tags_in_reverse_order():
    # Lauf: erst taggen (auf altem Pfad), dann umbenannt -> Undo: erst zurueck
    # benennen, dann Tags auf altem Pfad zuruecksetzen.
    tag = ChangeEntry(kind="tags", path="old.flac", before={"title": "A"},
                      after={"title": "B"})
    ren = ChangeEntry(kind="rename", old_path="old.flac", new_path="new.flac")
    order = []
    undo_run(
        _run("r1", [tag, ren]),
        write_tags=lambda p, s: order.append(("tags", p)),
        rename=lambda s, d: order.append(("rename", s, d)),
    )
    assert order == [("rename", "new.flac", "old.flac"), ("tags", "old.flac")]


def test_undo_collects_errors():
    entry = ChangeEntry(kind="tags", path="bad.flac", before={"title": "A"})

    def boom(path, snap):
        raise OSError("nope")

    ok, errors = undo_run(_run("r1", [entry]), write_tags=boom, rename=lambda s, d: None)
    assert ok == 0 and len(errors) == 1
