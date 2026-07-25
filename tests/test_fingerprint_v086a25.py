from __future__ import annotations

import io
import json
import subprocess

import pytest

from musictagstudio.providers import fingerprint


class _Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_find_fpcalc_prefers_explicit_path(tmp_path, monkeypatch):
    binary = tmp_path / "fpcalc.exe"
    binary.write_bytes(b"")
    monkeypatch.setattr(fingerprint.shutil, "which", lambda name: None)

    assert fingerprint.find_fpcalc(str(binary)) == str(binary)


def test_find_fpcalc_falls_back_to_path(monkeypatch):
    monkeypatch.setattr(
        fingerprint.shutil, "which", lambda name: "C:/tools/fpcalc.exe"
    )
    # Kein Bundle in diesem Test -> PATH greift.
    monkeypatch.setattr(fingerprint, "_VENDOR_DIR", fingerprint.Path("nope"))

    assert fingerprint.find_fpcalc("") == "C:/tools/fpcalc.exe"


def test_resolve_api_key_prefers_settings(monkeypatch):
    monkeypatch.setattr(fingerprint, "ACOUSTID_APP_KEY", "app-key")
    assert fingerprint.resolve_api_key("user-key") == "user-key"
    assert fingerprint.resolve_api_key("") == "app-key"


def test_compute_fingerprint_parses_json(monkeypatch):
    monkeypatch.setattr(fingerprint, "find_fpcalc", lambda p: "fpcalc")
    monkeypatch.setattr(
        fingerprint.subprocess,
        "run",
        lambda *a, **k: _Completed(
            stdout=json.dumps({"duration": 251.4, "fingerprint": "AQAB_x"})
        ),
    )

    result = fingerprint.compute_fingerprint("song.flac")

    assert result.duration == 251
    assert result.fingerprint == "AQAB_x"


def test_compute_fingerprint_without_fpcalc(monkeypatch):
    monkeypatch.setattr(fingerprint, "find_fpcalc", lambda p: None)

    with pytest.raises(fingerprint.FingerprintError, match="fpcalc"):
        fingerprint.compute_fingerprint("song.flac")


def test_compute_fingerprint_error_return(monkeypatch):
    monkeypatch.setattr(fingerprint, "find_fpcalc", lambda p: "fpcalc")
    monkeypatch.setattr(
        fingerprint.subprocess,
        "run",
        lambda *a, **k: _Completed(returncode=2, stderr="ERROR: no audio"),
    )

    with pytest.raises(fingerprint.FingerprintError, match="no audio"):
        fingerprint.compute_fingerprint("song.flac")


def test_compute_fingerprint_timeout(monkeypatch):
    monkeypatch.setattr(fingerprint, "find_fpcalc", lambda p: "fpcalc")

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("fpcalc", 120)

    monkeypatch.setattr(fingerprint.subprocess, "run", boom)

    with pytest.raises(fingerprint.FingerprintError):
        fingerprint.compute_fingerprint("song.flac")


def test_lookup_parses_recordings(monkeypatch):
    payload = {
        "status": "ok",
        "results": [
            {
                "score": 0.95,
                "recordings": [
                    {
                        "id": "mbid-1",
                        "title": "Lauf davon",
                        "artists": [{"name": "Danger Dan"}],
                    }
                ],
            },
            {
                "score": 0.4,
                "recordings": [{"id": "mbid-2", "title": "Andere"}],
            },
        ],
    }
    monkeypatch.setattr(
        fingerprint,
        "urlopen",
        lambda *a, **k: io.BytesIO(json.dumps(payload).encode("utf-8")),
    )

    matches = fingerprint.lookup("fp", 251, api_key="k")

    assert [m.recording_id for m in matches] == ["mbid-1", "mbid-2"]
    assert matches[0].score == 0.95
    assert matches[0].artist == "Danger Dan"


def test_lookup_surfaces_http_error_message(monkeypatch):
    from urllib.error import HTTPError

    body = io.BytesIO(
        json.dumps(
            {"error": {"code": 4, "message": "invalid API key"}, "status": "error"}
        ).encode("utf-8")
    )

    def raise_http(*a, **k):
        raise HTTPError("url", 400, "Bad Request", {}, body)

    monkeypatch.setattr(fingerprint, "urlopen", raise_http)

    with pytest.raises(fingerprint.FingerprintError, match="invalid API key"):
        fingerprint.lookup("fp", 100, api_key="k")


def test_lookup_requires_api_key():
    with pytest.raises(fingerprint.FingerprintError, match="API-Key"):
        fingerprint.lookup("fp", 100, api_key="")


def test_lookup_reports_api_error(monkeypatch):
    payload = {"status": "error", "error": {"message": "invalid client"}}
    monkeypatch.setattr(
        fingerprint,
        "urlopen",
        lambda *a, **k: io.BytesIO(json.dumps(payload).encode("utf-8")),
    )

    with pytest.raises(fingerprint.FingerprintError, match="invalid client"):
        fingerprint.lookup("fp", 100, api_key="k")


def test_identify_recording_end_to_end(monkeypatch):
    monkeypatch.setattr(
        fingerprint,
        "compute_fingerprint",
        lambda path, *, fpcalc_path="": fingerprint.FingerprintResult(200, "fp"),
    )
    payload = {
        "status": "ok",
        "results": [
            {"score": 0.9, "recordings": [{"id": "mbid-9", "title": "T"}]}
        ],
    }
    monkeypatch.setattr(
        fingerprint,
        "urlopen",
        lambda *a, **k: io.BytesIO(json.dumps(payload).encode("utf-8")),
    )

    matches = fingerprint.identify_recording("song.flac", api_key="k")
    assert matches[0].recording_id == "mbid-9"


def test_settings_round_trip_fingerprint(tmp_path):
    from musictagstudio.settings import AppSettings, load_settings, save_settings

    config = tmp_path / "config.toml"
    save_settings(
        AppSettings(acoustid_api_key="abc123", fpcalc_path="C:/fp/fpcalc.exe"),
        config,
    )
    loaded = load_settings(config)
    assert loaded.acoustid_api_key == "abc123"
    assert loaded.fpcalc_path == "C:/fp/fpcalc.exe"
