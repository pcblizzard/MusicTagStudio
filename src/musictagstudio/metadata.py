from pathlib import Path

from mutagen.flac import FLAC

from .song import Song


def get_first_tag(audio: FLAC, tag_name: str) -> str:
    """Liest den ersten Wert eines FLAC-Tags."""
    values = audio.get(tag_name)

    if not values:
        return ""

    return str(values[0])


def split_number(value: str) -> tuple[str, str]:
    """
    Zerlegt Werte wie '3/20' in Nummer und Gesamtzahl.

    '3/20' -> ('3', '20')
    '3'    -> ('3', '')
    """
    if "/" not in value:
        return value.strip(), ""

    number, total = value.split("/", maxsplit=1)

    return number.strip(), total.strip()


def read_metadata(filepath: str | Path) -> Song:
    """Liest die Metadaten einer FLAC-Datei als Song-Objekt."""
    path = Path(filepath)
    audio = FLAC(path)

    track, total_tracks = split_number(
        get_first_tag(audio, "tracknumber")
    )

    disc, total_discs = split_number(
        get_first_tag(audio, "discnumber")
    )

    return Song(
        title=get_first_tag(audio, "title"),
        artist=get_first_tag(audio, "artist"),
        album_artist=get_first_tag(audio, "albumartist"),
        album=get_first_tag(audio, "album"),
        genre=get_first_tag(audio, "genre"),
        year=get_first_tag(audio, "date"),
        track=track,
        total_tracks=total_tracks,
        disc=disc,
        total_discs=total_discs,
        comment=get_first_tag(audio, "comment"),
        path=str(path),
    )