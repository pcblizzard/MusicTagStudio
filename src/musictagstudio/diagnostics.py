from __future__ import annotations

import logging
from pathlib import Path


_LOGGERS: dict[str, logging.Logger] = {}


def get_diagnostic_logger(
    name: str,
) -> logging.Logger:
    existing = _LOGGERS.get(name)

    if existing is not None:
        return existing

    log_directory = (
        Path.cwd()
        / "logs"
    )
    log_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    logger = logging.getLogger(
        f"musictagstudio.{name}"
    )
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(
            log_directory
            / f"{name}.log",
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s"
            )
        )
        logger.addHandler(handler)

    _LOGGERS[name] = logger

    return logger
