from __future__ import annotations

from pathlib import Path

from mutagen.flac import FLAC

from ..models.song import Song


def get_first_tag(audio: FLAC, tag_name: str) -> str:
    values = audio.get(tag_name)
    return str(values[0]) if values else ""


def get_first_available_tag(audio: FLAC, names: tuple[str, ...]) -> str:
    for name in names:
        value = get_first_tag(audio, name)
        if value:
            return value
    return ""


def split_number(value: str) -> tuple[str, str]:
    if "/" not in value:
        return value.strip(), ""
    number, total = value.split("/", 1)
    return number.strip(), total.strip()


def read_metadata(filepath: str | Path) -> Song:
    path = Path(filepath)
    audio = FLAC(path)
    track, total_tracks = split_number(get_first_tag(audio, "tracknumber"))
    disc, total_discs = split_number(get_first_tag(audio, "discnumber"))
    return Song(
        title=get_first_tag(audio, "title"),
        artist=get_first_tag(audio, "artist"),
        album_artist=get_first_available_tag(audio, ("albumartist", "album artist", "album_artist")),
        album=get_first_tag(audio, "album"),
        genre=get_first_tag(audio, "genre"),
        year=get_first_tag(audio, "date"),
        track=track,
        total_tracks=total_tracks,
        disc=disc,
        total_discs=total_discs,
        isrc=get_first_tag(audio, "isrc"),
        label=get_first_available_tag(audio, ("organization", "label", "publisher")),
        copyright=get_first_tag(audio, "copyright"),
        composer=get_first_tag(audio, "composer"),
        comment=get_first_tag(audio, "comment"),
        path=str(path),
    )


def combine_number(number: str, total: str) -> str:
    number = number.strip()
    total = total.strip()
    if not number:
        return ""
    return f"{number}/{total}" if total else number


def set_tag(audio: FLAC, name: str, value: str) -> None:
    value = value.strip()
    if value:
        audio[name] = value
    elif name in audio:
        del audio[name]


def save_song_metadata(filepath: str | Path, song: Song) -> None:
    audio = FLAC(filepath)
    for name, value in (
        ("title", song.title),
        ("artist", song.artist),
        ("albumartist", song.album_artist),
        ("album", song.album),
        ("genre", song.genre),
        ("date", song.year),
        ("tracknumber", combine_number(song.track, song.total_tracks)),
        ("discnumber", combine_number(song.disc, song.total_discs)),
        ("isrc", song.isrc),
        ("organization", song.label),
        ("copyright", song.copyright),
        ("composer", song.composer),
        ("comment", song.comment),
    ):
        set_tag(audio, name, value)
    audio.save()
