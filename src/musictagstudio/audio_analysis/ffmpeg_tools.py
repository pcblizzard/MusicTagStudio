from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .models import FFmpegInstallation


def find_ffmpeg(
    configured_directory: str = "",
) -> FFmpegInstallation:
    candidates: list[
        tuple[str | None, str | None]
    ] = []

    if configured_directory.strip():
        directory = Path(
            configured_directory
        )
        candidates.append(
            (
                str(
                    directory
                    / executable_name("ffmpeg")
                ),
                str(
                    directory
                    / executable_name("ffprobe")
                ),
            )
        )

    bundled_directory = (
        application_root()
        / "tools"
        / "ffmpeg"
    )

    candidates.append(
        (
            str(
                bundled_directory
                / executable_name("ffmpeg")
            ),
            str(
                bundled_directory
                / executable_name("ffprobe")
            ),
        )
    )

    candidates.append(
        (
            shutil.which("ffmpeg"),
            shutil.which("ffprobe"),
        )
    )

    for ffmpeg_path, ffprobe_path in candidates:
        if not (
            ffmpeg_path
            and ffprobe_path
        ):
            continue

        if not (
            Path(ffmpeg_path).is_file()
            and Path(ffprobe_path).is_file()
        ):
            continue

        version = read_ffmpeg_version(
            ffmpeg_path
        )

        return FFmpegInstallation(
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,
            version=version,
        )

    return FFmpegInstallation(
        ffmpeg_path="",
        ffprobe_path="",
        version="",
    )


def read_ffmpeg_version(
    ffmpeg_path: str,
) -> str:
    try:
        completed = subprocess.run(
            [
                ffmpeg_path,
                "-version",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=_creation_flags(),
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return ""

    first_line = (
        completed.stdout.splitlines()[0]
        if completed.stdout
        else ""
    )
    match = re.search(
        r"ffmpeg version\s+([^\s]+)",
        first_line,
        re.IGNORECASE,
    )

    return (
        match.group(1)
        if match
        else first_line.strip()
    )


def find_ffprobe() -> str:
    """Pfad zu ffprobe: mitgeliefert (tools/ffmpeg/) bevorzugt, sonst PATH."""
    bundled = (
        application_root()
        / "tools"
        / "ffmpeg"
        / executable_name("ffprobe")
    )
    if bundled.is_file():
        return str(bundled)
    return shutil.which("ffprobe") or ""


def application_root() -> Path:
    return Path(__file__).resolve().parents[3]


def executable_name(
    base_name: str,
) -> str:
    if os.name == "nt":
        return f"{base_name}.exe"

    return base_name


def _creation_flags() -> int:
    return int(
        getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )
    )
