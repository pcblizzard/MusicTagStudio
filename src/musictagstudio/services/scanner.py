from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..diagnostics import get_diagnostic_logger
from ..models.song import Song
from .metadata_io import (
    SUPPORTED_AUDIO_EXTENSIONS,
    read_metadata,
)


@dataclass(frozen=True)
class ScanFailure:
    path: str
    error: str


@dataclass(frozen=True)
class ScanResult:
    songs: tuple[Song, ...]
    detected_files: int
    failures: tuple[ScanFailure, ...]

    @property
    def successful_files(self) -> int:
        return len(self.songs)


def scan_folder_detailed(
    folder: str | Path,
) -> ScanResult:
    folder_path = Path(folder)

    if not folder_path.is_dir():
        return ScanResult(
            songs=(),
            detected_files=0,
            failures=(),
        )

    files = sorted(
        (
            path
            for path in folder_path.rglob("*")
            if (
                path.is_file()
                and path.suffix.lower()
                in SUPPORTED_AUDIO_EXTENSIONS
            )
        ),
        key=lambda item: str(item).casefold(),
    )
    songs: list[Song] = []
    failures: list[ScanFailure] = []
    logger = get_diagnostic_logger(
        "scanner"
    )
    logger.info(
        "Scan gestartet: %s | %d erkannte Datei(en)",
        folder_path,
        len(files),
    )

    for filepath in files:
        try:
            songs.append(
                read_metadata(filepath)
            )
        except Exception as error:
            logger.exception(
                "Datei konnte nicht eingelesen werden: %s",
                filepath,
            )
            failures.append(
                ScanFailure(
                    path=str(filepath),
                    error=(
                        f"{type(error).__name__}: "
                        f"{error}"
                    ),
                )
            )

    logger.info(
        "Scan beendet: %d eingelesen, %d übersprungen",
        len(songs),
        len(failures),
    )

    return ScanResult(
        songs=tuple(songs),
        detected_files=len(files),
        failures=tuple(failures),
    )


def scan_folder(
    folder: str | Path,
) -> list[Song]:
    return list(
        scan_folder_detailed(
            folder
        ).songs
    )
