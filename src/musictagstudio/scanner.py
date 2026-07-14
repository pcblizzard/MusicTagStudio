from pathlib import Path
from .metadata import read_metadata


def scan_folder(folder):
    files = []

    for file in Path(folder).rglob("*.flac"):
        files.append(read_metadata(str(file)))

    return files