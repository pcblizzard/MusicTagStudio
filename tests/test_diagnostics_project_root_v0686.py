from pathlib import Path

from musictagstudio import diagnostics


def test_project_root_uses_pyproject(
    monkeypatch,
    tmp_path,
):
    project = (
        tmp_path
        / "project"
    )
    nested = (
        project
        / "a"
        / "b"
    )
    nested.mkdir(
        parents=True
    )
    (
        project
        / "pyproject.toml"
    ).write_text(
        "[project]\nname='x'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(nested)

    assert (
        diagnostics.project_root()
        == project
    )


def test_session_id_is_not_empty():
    assert (
        diagnostics.current_session_id()
    )
