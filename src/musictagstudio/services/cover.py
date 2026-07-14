from pathlib import Path

from mutagen.flac import FLAC


def load_cover(filepath: str | Path) -> bytes | None:
    path = Path(filepath)
    if not path.is_file():
        return None
    audio = FLAC(path)
    return audio.pictures[0].data if audio.pictures else None
