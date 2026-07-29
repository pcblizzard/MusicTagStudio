from __future__ import annotations

from pathlib import Path

import musictagstudio.diagnostics as diagnostics


def test_user_data_dir_uses_localappdata(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    target = diagnostics.user_data_dir()
    assert target == tmp_path / "MusicTagStudio"
    assert target.is_dir()  # wird bei Bedarf angelegt


def test_project_root_is_user_dir_when_frozen(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(diagnostics, "is_frozen", lambda: True)
    assert diagnostics.project_root() == tmp_path / "MusicTagStudio"


def test_project_root_is_repo_in_dev():
    # Im Entwicklungsbetrieb (nicht frozen) liegt eine pyproject.toml darüber.
    assert not diagnostics.is_frozen()
    assert (diagnostics.project_root() / "pyproject.toml").is_file()


def test_resource_root_uses_meipass_when_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics, "is_frozen", lambda: True)
    monkeypatch.setattr(diagnostics.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert diagnostics.resource_root() == tmp_path


def test_resource_root_is_repo_in_dev():
    assert diagnostics.resource_root() == Path(diagnostics.__file__).resolve().parents[2]
