from pathlib import Path

from ..models.song import Song
from .metadata_io import SUPPORTED_AUDIO_EXTENSIONS, read_metadata


def scan_folder(folder: str | Path) -> list[Song]:
    folder_path = Path(folder)
    if not folder_path.is_dir():
        return []
    files = sorted(
        (path for path in folder_path.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS),
        key=lambda item: str(item).casefold(),
    )
    songs: list[Song] = []
    for filepath in files:
        try:
            songs.append(read_metadata(filepath))
        except Exception as error:
            print(f"Datei übersprungen: {filepath}\nGrund: {error}")
    return songs
