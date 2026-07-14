from pathlib import Path

from ..models.song import Song
from .metadata_io import read_metadata


def scan_folder(folder: str | Path) -> list[Song]:
    folder_path = Path(folder)
    if not folder_path.is_dir():
        return []
    songs: list[Song] = []
    for filepath in sorted(folder_path.rglob("*.flac"), key=lambda item: str(item).lower()):
        try:
            songs.append(read_metadata(filepath))
        except Exception as error:
            print(f"Datei übersprungen: {filepath}\nGrund: {error}")
    return songs
