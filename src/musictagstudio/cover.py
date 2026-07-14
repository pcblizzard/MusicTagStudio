from pathlib import Path

from mutagen.flac import FLAC


def load_cover(filepath: str) -> bytes | None:
    """
    Liest das erste eingebettete Cover aus einer FLAC-Datei.

    Gibt die Bilddaten als Bytes zurück.
    Falls kein Cover vorhanden ist, wird None zurückgegeben.
    """
    path = Path(filepath)

    if not path.is_file():
        return None

    audio = FLAC(path)

    if not audio.pictures:
        return None

    return audio.pictures[0].data