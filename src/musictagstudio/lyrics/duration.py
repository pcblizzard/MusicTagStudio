from __future__ import annotations

from pathlib import Path

from mutagen import File, MutagenError


def read_duration_seconds(audio_path: str | Path) -> float:
    try:
        audio = File(str(audio_path), easy=False)
        length = float(getattr(getattr(audio, "info", None), "length", 0) or 0)
    except (MutagenError, OSError, TypeError, ValueError):
        return 0.0
    return length if length > 0 else 0.0
