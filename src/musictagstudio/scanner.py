from pathlib import Path


def scan_music_folder(folder_path):
    """
    Durchsucht einen Ordner nach FLAC-Dateien.

    Gibt eine Liste mit gefundenen Dateien zurück.
    """

    folder = Path(folder_path)

    if not folder.exists():
        return []

    flac_files = list(folder.rglob("*.flac"))

    return flac_files