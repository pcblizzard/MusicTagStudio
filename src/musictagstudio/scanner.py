from pathlib import Path

from .metadata import read_metadata
from .song import Song


def scan_folder(folder: str | Path) -> list[Song]:
    """Durchsucht einen Ordner und alle Unterordner nach FLAC-Dateien."""
    folder_path = Path(folder)

    if not folder_path.is_dir():
        return []

    songs: list[Song] = []

    flac_files = sorted(
        folder_path.rglob("*.flac"),
        key=lambda path: str(path).lower(),
    )

    for filepath in flac_files:
        try:
            songs.append(read_metadata(filepath))
        except Exception as error:
            print(f"Datei übersprungen: {filepath}")
            print(f"Grund: {error}")

    return songs