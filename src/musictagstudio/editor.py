from pathlib import Path

from mutagen.flac import FLAC

from .song import Song


def combine_number(number: str, total: str) -> str:
    """
    Verbindet Nummer und Gesamtzahl.

    Beispiele:
    3 + 20 -> 3/20
    3 + leer -> 3
    leer + leer -> leer
    """
    number = number.strip()
    total = total.strip()

    if not number:
        return ""

    if total:
        return f"{number}/{total}"

    return number


def set_tag(audio: FLAC, tag_name: str, value: str) -> None:
    """
    Schreibt einen FLAC-Tag.

    Ein leeres Feld entfernt den vorhandenen Tag.
    """
    value = value.strip()

    if value:
        audio[tag_name] = value
    elif tag_name in audio:
        del audio[tag_name]


def save_song_metadata(filepath: str | Path, song: Song) -> None:
    """Speichert die bearbeitbaren Metadaten eines Song-Objekts."""
    audio = FLAC(filepath)

    set_tag(audio, "title", song.title)
    set_tag(audio, "artist", song.artist)
    set_tag(audio, "albumartist", song.album_artist)
    set_tag(audio, "album", song.album)
    set_tag(audio, "genre", song.genre)
    set_tag(audio, "date", song.year)

    track_value = combine_number(
        song.track,
        song.total_tracks,
    )

    disc_value = combine_number(
        song.disc,
        song.total_discs,
    )

    set_tag(audio, "tracknumber", track_value)
    set_tag(audio, "discnumber", disc_value)

    set_tag(audio, "isrc", song.isrc)
    set_tag(audio, "organization", song.label)
    set_tag(audio, "copyright", song.copyright)
    set_tag(audio, "composer", song.composer)

    set_tag(audio, "comment", song.comment)

    audio.save()
