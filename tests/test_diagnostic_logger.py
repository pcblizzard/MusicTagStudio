from musictagstudio import diagnostics


def test_diagnostic_logger_creates_log_file(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    diagnostics._LOGGERS.clear()

    logger = (
        diagnostics.get_diagnostic_logger(
            "example"
        )
    )
    logger.error("Test")

    for handler in logger.handlers:
        handler.flush()

    assert (
        tmp_path
        / "logs"
        / "example.log"
    ).exists()
