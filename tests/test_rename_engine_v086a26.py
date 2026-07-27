from __future__ import annotations

from pathlib import Path

from musictagstudio.models.song import Song
from musictagstudio.services.rename import (
    DEFAULT_PATTERN,
    build_new_name,
    build_new_stem,
    plan_renames,
)


def _song(path: str, **fields) -> Song:
    return Song(path=path, **fields)


def test_default_pattern_pads_track_and_keeps_extension():
    song = _song("C:/m/x.flac", track="1", title="Eine aufs Maul")
    assert build_new_stem(song, DEFAULT_PATTERN) == "01 - Eine aufs Maul"
    assert build_new_name(song, DEFAULT_PATTERN) == "01 - Eine aufs Maul.flac"


def test_two_digit_track_is_left_untouched():
    song = _song("C:/m/x.mp3", track="12", title="Song")
    assert build_new_stem(song, "{track} - {title}") == "12 - Song"


def test_forbidden_characters_are_sanitized():
    song = _song("C:/m/x.flac", track="3", title='A/B:C?"D*')
    stem = build_new_stem(song, "{track} - {title}")
    assert "/" not in stem and ":" not in stem and "?" not in stem
    assert stem == "03 - A_B_C__D_"


def test_unknown_token_stays_literal():
    song = _song("C:/m/x.flac", track="1", title="T")
    assert build_new_stem(song, "{track} {unknown}") == "01 {unknown}"


def test_broken_pattern_falls_back_to_original_stem():
    song = _song("C:/m/original.flac", title="T")
    assert build_new_stem(song, "{track") == "original"


def test_empty_result_falls_back_to_original_stem():
    song = _song("C:/m/keepme.flac")  # alle Felder leer
    assert build_new_stem(song, "{title}") == "keepme"


def test_multiple_fields_and_whitespace_collapse():
    song = _song(
        "C:/m/x.flac",
        track="2",
        artist="Danger Dan",
        title="Reflexionen",
    )
    assert build_new_stem(song, "{track}  -   {artist} - {title}") == (
        "02 - Danger Dan - Reflexionen"
    )


def test_plan_marks_unchanged():
    song = _song("C:/m/01 - Song.flac", track="1", title="Song")
    (plan,) = plan_renames([song], "{track} - {title}")
    assert plan.applies is False and plan.reason == "unchanged"


def test_plan_detects_collision_within_selection():
    a = _song("C:/m/a.flac", track="1", title="Same")
    b = _song("C:/m/b.flac", track="1", title="Same")
    plans = plan_renames([a, b], "{track} - {title}")
    assert plans[0].applies is True and plans[0].reason == "ok"
    assert plans[1].applies is False and plans[1].reason == "collision"


def test_plan_detects_existing_target(tmp_path: Path):
    (tmp_path / "01 - Song.flac").write_bytes(b"x")
    source = tmp_path / "raw.flac"
    source.write_bytes(b"y")
    song = _song(str(source), track="1", title="Song")
    (plan,) = plan_renames([song], "{track} - {title}")
    assert plan.applies is False and plan.reason == "target_exists"


def test_plan_ok_for_changed_name(tmp_path: Path):
    source = tmp_path / "raw.flac"
    source.write_bytes(b"y")
    song = _song(str(source), track="7", title="Neu")
    (plan,) = plan_renames([song], "{track} - {title}")
    assert plan.applies is True and plan.reason == "ok"
    assert plan.new_name == "07 - Neu.flac"


def test_plan_handles_missing_path():
    (plan,) = plan_renames([Song(title="X")], "{title}")
    assert plan.applies is False and plan.reason == "no_path"
