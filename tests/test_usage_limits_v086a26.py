from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from musictagstudio.usage_limits import (
    FREE_RENAME_LIMIT,
    TRIAL_DAYS,
    ensure_trial_started,
    record_renames,
    remaining_free_renames,
    renames_used,
    trial_active,
    trial_days_remaining,
    trial_started_at,
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


# --- Testphase (zeitbasiert) -------------------------------------------------


def test_trial_inactive_before_start(tmp_path: Path):
    p = tmp_path / "trial.json"
    now = datetime(2026, 1, 1, 12, 0, 0)
    assert trial_started_at(p) is None
    assert trial_active(now, p) is False
    assert trial_days_remaining(now, p) == 0


def test_ensure_trial_started_is_idempotent(tmp_path: Path):
    p = tmp_path / "trial.json"
    first = datetime(2026, 1, 1, 8, 0, 0)
    ensure_trial_started(first, p)
    started = trial_started_at(p)
    # Ein zweiter Aufruf (später) verschiebt den Start nicht.
    ensure_trial_started(first + timedelta(days=5), p)
    assert trial_started_at(p) == started


def test_trial_active_within_window_then_expires(tmp_path: Path):
    p = tmp_path / "trial.json"
    start = datetime(2026, 1, 1, 8, 0, 0)
    ensure_trial_started(start, p)
    assert trial_active(start, p) is True
    assert trial_active(start + timedelta(days=TRIAL_DAYS) - timedelta(seconds=1), p)
    # Genau am Ende noch nicht abgelaufen, danach schon.
    assert trial_active(start + timedelta(days=TRIAL_DAYS), p) is True
    assert trial_active(start + timedelta(days=TRIAL_DAYS, seconds=1), p) is False


def test_trial_days_remaining_counts_partial_day(tmp_path: Path):
    p = tmp_path / "trial.json"
    start = datetime(2026, 1, 1, 8, 0, 0)
    ensure_trial_started(start, p)
    assert trial_days_remaining(start, p) == TRIAL_DAYS
    # Nach 1,5 Tagen bleiben (angebrochen) noch 2 Tage.
    assert trial_days_remaining(start + timedelta(days=1, hours=12), p) == 2
    assert trial_days_remaining(start + timedelta(days=TRIAL_DAYS), p) == 0


def test_trial_and_renames_coexist_in_one_file(tmp_path: Path):
    # record_renames darf den Testphasen-Start nicht überschreiben und umgekehrt.
    p = tmp_path / "trial.json"
    start = datetime(2026, 1, 1, 8, 0, 0)
    ensure_trial_started(start, p)
    record_renames(4, p)
    assert renames_used(p) == 4
    assert trial_started_at(p) == start
