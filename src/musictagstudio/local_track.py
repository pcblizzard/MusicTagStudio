from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re

from mutagen import File as MutagenFile


def title_from_filename(filepath: str) -> str:
    """Derive a conservative track-title fallback from a local file name."""
    if not filepath:
        return ""
    filename = str(filepath).replace("\\", "/").rsplit("/", 1)[-1]
    stem = Path(filename).stem
    stem = re.sub(
        r"^\s*(?:\d{1,2}[-_.])?\d{1,3}\s*[.)_-]\s*",
        "",
        stem,
    )
    if " - " in stem:
        stem = stem.split(" - ", 1)[1]
    return stem.strip()


@lru_cache(maxsize=4096)
def local_duration_ms(filepath: str) -> int | None:
    """Read a local track duration once and return milliseconds."""
    path = Path(filepath)
    if not path.is_file():
        return None
    try:
        audio = MutagenFile(path)
    except Exception:
        return None
    length = getattr(getattr(audio, "info", None), "length", None)
    if length is None:
        return None
    try:
        return round(float(length) * 1000)
    except (TypeError, ValueError):
        return None
