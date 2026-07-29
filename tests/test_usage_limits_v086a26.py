from __future__ import annotations

from pathlib import Path

from musictagstudio.usage_limits import (
    FREE_RENAME_LIMIT,
    record_renames,
    remaining_free_renames,
    renames_used,
)


def test_starts_empty(tmp_path: Path):
    p = tmp_path / "usage.json"
    assert renames_used(p) == 0
    assert remaining_free_renames(p) == FREE_RENAME_LIMIT


def test_record_accumulates(tmp_path: Path):
    p = tmp_path / "usage.json"
    record_renames(5, p)
    record_renames(3, p)
    assert renames_used(p) == 8
    assert remaining_free_renames(p) == FREE_RENAME_LIMIT - 8


def test_remaining_never_negative(tmp_path: Path):
    p = tmp_path / "usage.json"
    record_renames(FREE_RENAME_LIMIT + 10, p)
    assert remaining_free_renames(p) == 0


def test_corrupt_file_reads_zero(tmp_path: Path):
    p = tmp_path / "usage.json"
    p.write_text("not json", encoding="utf-8")
    assert renames_used(p) == 0


def test_negative_count_ignored(tmp_path: Path):
    p = tmp_path / "usage.json"
    record_renames(-5, p)
    assert renames_used(p) == 0
