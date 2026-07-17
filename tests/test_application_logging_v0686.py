from musictagstudio import diagnostics


def test_application_start_writes_log(
    monkeypatch,
    tmp_path,
):
    project = tmp_path / "project"
    project.mkdir()
    (
        project
        / "pyproject.toml"
    ).write_text(
        "[project]\nname='x'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)

    for logger in (
        diagnostics._LOGGERS.values()
    ):
        for handler in logger.handlers:
            handler.close()

    diagnostics._LOGGERS.clear()
    diagnostics.log_application_start(
        version="test",
    )

    logger = (
        diagnostics.get_diagnostic_logger(
            "application"
        )
    )

    for handler in logger.handlers:
        handler.flush()

    content = (
        project
        / "logs"
        / "application.log"
    ).read_text(
        encoding="utf-8"
    )

    assert "PROGRAMMSTART" in content
    assert "Version=test" in content
    assert "session=" in content
