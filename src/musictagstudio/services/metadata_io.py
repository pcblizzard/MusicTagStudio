from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess

from mutagen.apev2 import APEv2, APETextValue
from mutagen.asf import ASF
from mutagen.flac import FLAC
from mutagen.id3 import (
    COMM,
    ID3,
    ID3NoHeaderError,
    TALB,
    TCOM,
    TCON,
    TCOP,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TPOS,
    TRCK,
    TSRC,
    TXXX,
)
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wavpack import WavPack

from ..diagnostics import get_diagnostic_logger
from ..models.song import Song


SUPPORTED_AUDIO_EXTENSIONS = {
    ".flac",
    ".wv",
    ".mp3",
    ".ogg",
    ".oga",
    ".opus",
    ".m4a",
    ".m4b",
    ".mp4",
    ".ape",
    ".wma",
    ".asf",
}


def split_number(
    value: str,
) -> tuple[str, str]:
    value = str(
        value or ""
    ).strip()

    if "/" not in value:
        return value, ""

    number, total = value.split(
        "/",
        1,
    )

    return (
        number.strip(),
        total.strip(),
    )


def combine_number(
    number: str,
    total: str,
) -> str:
    number = str(
        number or ""
    ).strip()
    total = str(
        total or ""
    ).strip()

    if not number:
        return ""

    return (
        f"{number}/{total}"
        if total
        else number
    )


def read_metadata(
    filepath: str | Path,
) -> Song:
    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix == ".flac":
        return _read_vorbis(
            path,
            FLAC(path),
        )

    if suffix == ".wv":
        return _read_wavpack_apev2(
            path
        )

    if suffix == ".ape":
        return _read_ape_file(
            path
        )

    if suffix in {
        ".wma",
        ".asf",
    }:
        return _read_asf(
            path
        )

    if suffix in {
        ".ogg",
        ".oga",
    }:
        return _read_vorbis(
            path,
            OggVorbis(path),
        )

    if suffix == ".opus":
        return _read_vorbis(
            path,
            OggOpus(path),
        )

    if suffix == ".mp3":
        return _read_mp3(path)

    if suffix in {
        ".m4a",
        ".m4b",
        ".mp4",
    }:
        return _read_mp4(path)

    raise ValueError(
        f"Nicht unterstütztes Audioformat: {suffix}"
    )


def save_song_metadata(
    filepath: str | Path,
    song: Song,
) -> None:
    path = Path(filepath)
    suffix = path.suffix.lower()

    if suffix == ".flac":
        audio = FLAC(path)
        _write_vorbis(
            audio,
            song,
        )
        audio.save()
        return

    if suffix == ".wv":
        _write_wavpack_apev2(
            path,
            song,
        )
        return

    if suffix == ".ape":
        _write_ape_file(
            path,
            song,
        )
        return

    if suffix in {
        ".wma",
        ".asf",
    }:
        _write_asf(
            path,
            song,
        )
        return

    if suffix in {
        ".ogg",
        ".oga",
    }:
        audio = OggVorbis(path)
        _write_vorbis(
            audio,
            song,
        )
        audio.save()
        return

    if suffix == ".opus":
        audio = OggOpus(path)
        _write_vorbis(
            audio,
            song,
        )
        audio.save()
        return

    if suffix == ".mp3":
        _write_mp3(
            path,
            song,
        )
        return

    if suffix in {
        ".m4a",
        ".m4b",
        ".mp4",
    }:
        _write_mp4(
            path,
            song,
        )
        return

    raise ValueError(
        f"Nicht unterstütztes Audioformat: {suffix}"
    )


def _first(
    tags,
    *names: str,
) -> str:
    for name in names:
        values = tags.get(name)

        if values:
            value = (
                values[0]
                if isinstance(
                    values,
                    list,
                )
                else values
            )

            return str(value)

    return ""


def _read_vorbis(
    path: Path,
    audio,
) -> Song:
    track, total_tracks = split_number(
        _first(
            audio,
            "tracknumber",
        )
    )
    disc, total_discs = split_number(
        _first(
            audio,
            "discnumber",
        )
    )

    return Song(
        title=_first(
            audio,
            "title",
        ),
        artist=_first(
            audio,
            "artist",
        ),
        album_artist=_first(
            audio,
            "albumartist",
            "album artist",
            "album_artist",
        ),
        album=_first(
            audio,
            "album",
        ),
        genre=_first(
            audio,
            "genre",
        ),
        year=_first(
            audio,
            "date",
        ),
        track=track,
        total_tracks=total_tracks,
        disc=disc,
        total_discs=total_discs,
        isrc=_first(
            audio,
            "isrc",
        ),
        label=_first(
            audio,
            "organization",
            "label",
            "publisher",
        ),
        copyright=_first(
            audio,
            "copyright",
        ),
        composer=_first(
            audio,
            "composer",
        ),
        comment=_first(
            audio,
            "comment",
            "description",
        ),
        path=str(path),
    )


def _write_vorbis(
    audio,
    song: Song,
) -> None:
    values = {
        "title": song.title,
        "artist": song.artist,
        "albumartist": (
            song.album_artist
        ),
        "album": song.album,
        "genre": song.genre,
        "date": song.year,
        "tracknumber": combine_number(
            song.track,
            song.total_tracks,
        ),
        "discnumber": combine_number(
            song.disc,
            song.total_discs,
        ),
        "isrc": song.isrc,
        "organization": song.label,
        "copyright": song.copyright,
        "composer": song.composer,
        "comment": song.comment,
    }

    for key, value in values.items():
        value = str(
            value or ""
        ).strip()

        if value:
            audio[key] = [value]
        elif key in audio:
            del audio[key]


def _ape_first(
    tags,
    *names: str,
) -> str:
    if tags is None:
        return ""

    for name in names:
        value = tags.get(name)

        if value is None:
            continue

        if isinstance(
            value,
            APETextValue,
        ):
            return str(value)

        if isinstance(
            value,
            (list, tuple),
        ):
            return (
                str(value[0])
                if value
                else ""
            )

        return str(value)

    return ""



def _read_wavpack_apev2(
    path: Path,
) -> Song:
    """
    Liest WavPack-Tags ohne den Scan wegen eines einzelnen Parserfehlers
    abzubrechen.

    Reihenfolge:
    1. APEv2 direkt
    2. WavPack über Mutagen
    3. ffprobe-Tags als sichere Lesefallback-Lösung
    """
    logger = get_diagnostic_logger(
        "wavpack"
    )

    try:
        tags = APEv2(path)

        return _song_from_ape_tags(
            path,
            tags,
        )
    except Exception:
        logger.exception(
            "Direkter APEv2-Leser fehlgeschlagen: %s",
            path,
        )

    try:
        audio = WavPack(path)

        return _song_from_ape_tags(
            path,
            audio.tags or {},
        )
    except Exception:
        logger.exception(
            "Mutagen-WavPack-Leser fehlgeschlagen: %s",
            path,
        )

    tags = _read_ffprobe_tags(
        path
    )

    if tags:
        logger.info(
            "WavPack-Tags über ffprobe gelesen: %s",
            path,
        )

        return _song_from_mapping(
            path,
            tags,
        )

    raise ValueError(
        "WavPack-Datei erkannt, aber weder APEv2, "
        "Mutagen noch ffprobe konnten Metadaten lesen. "
        "Details stehen in logs/wavpack.log."
    )


def _song_from_ape_tags(
    path: Path,
    tags,
) -> Song:
    class _ApeContainer:
        def __init__(self, value):
            self.tags = value

    return _read_apev2(
        path,
        _ApeContainer(tags),
    )


def _read_ffprobe_tags(
    path: Path,
) -> dict[str, str]:
    executable = shutil.which(
        "ffprobe"
    )

    if executable is None:
        return {}

    command = [
        executable,
        "-v",
        "error",
        "-show_entries",
        "format_tags",
        "-of",
        "json",
        str(path),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ):
        get_diagnostic_logger(
            "wavpack"
        ).exception(
            "ffprobe konnte nicht gestartet werden: %s",
            path,
        )

        return {}

    if completed.returncode != 0:
        get_diagnostic_logger(
            "wavpack"
        ).error(
            "ffprobe-Fehler für %s: %s",
            path,
            completed.stderr.strip(),
        )

        return {}

    try:
        payload = json.loads(
            completed.stdout
        )
    except json.JSONDecodeError:
        get_diagnostic_logger(
            "wavpack"
        ).exception(
            "Ungültige ffprobe-JSON-Antwort: %s",
            path,
        )

        return {}

    raw_tags = (
        payload.get(
            "format",
            {},
        ).get(
            "tags",
            {},
        )
    )

    return {
        str(key).casefold(): str(value)
        for key, value
        in raw_tags.items()
    }


def _song_from_mapping(
    path: Path,
    tags: dict[str, str],
) -> Song:
    def value(
        *names: str,
    ) -> str:
        for name in names:
            found = tags.get(
                name.casefold()
            )

            if found is not None:
                return str(found)

        return ""

    track, total_tracks = split_number(
        value(
            "track",
            "tracknumber",
        )
    )
    disc, total_discs = split_number(
        value(
            "disc",
            "discnumber",
        )
    )

    return Song(
        title=value("title"),
        artist=value("artist"),
        album_artist=value(
            "album artist",
            "albumartist",
            "album_artist",
        ),
        album=value("album"),
        genre=value("genre"),
        year=value(
            "year",
            "date",
        ),
        track=track,
        total_tracks=total_tracks,
        disc=disc,
        total_discs=total_discs,
        isrc=value("isrc"),
        label=value(
            "label",
            "publisher",
            "organization",
        ),
        copyright=value(
            "copyright"
        ),
        composer=value(
            "composer"
        ),
        comment=value(
            "comment",
            "commentary",
            "description",
        ),
        path=str(path),
    )



def _read_ape_file(
    path: Path,
) -> Song:
    try:
        tags = APEv2(path)
    except Exception as error:
        raise ValueError(
            "Monkey's-Audio-Datei erkannt, aber die APEv2-Tags "
            "konnten nicht gelesen werden."
        ) from error

    return _song_from_ape_tags(
        path,
        tags,
    )


def _write_ape_file(
    path: Path,
    song: Song,
) -> None:
    try:
        tags = APEv2(path)
    except Exception:
        tags = APEv2()

    _write_apev2(
        tags,
        song,
    )
    tags.save(path)


def _asf_first(
    tags,
    *names: str,
) -> str:
    for name in names:
        values = tags.get(name)

        if not values:
            continue

        value = values[0]

        if hasattr(
            value,
            "value",
        ):
            value = value.value

        return str(value)

    return ""


def _read_asf(
    path: Path,
) -> Song:
    audio = ASF(path)
    tags = audio.tags or {}
    track, total_tracks = split_number(
        _asf_first(
            tags,
            "WM/TrackNumber",
            "WM/Track",
        )
    )
    disc, total_discs = split_number(
        _asf_first(
            tags,
            "WM/PartOfSet",
        )
    )

    return Song(
        title=_asf_first(
            tags,
            "Title",
        ),
        artist=_asf_first(
            tags,
            "Author",
            "WM/AlbumArtist",
        ),
        album_artist=_asf_first(
            tags,
            "WM/AlbumArtist",
        ),
        album=_asf_first(
            tags,
            "WM/AlbumTitle",
        ),
        genre=_asf_first(
            tags,
            "WM/Genre",
        ),
        year=_asf_first(
            tags,
            "WM/Year",
        ),
        track=track,
        total_tracks=total_tracks,
        disc=disc,
        total_discs=total_discs,
        isrc=_asf_first(
            tags,
            "WM/ISRC",
        ),
        label=_asf_first(
            tags,
            "WM/Publisher",
        ),
        copyright=_asf_first(
            tags,
            "Copyright",
        ),
        composer=_asf_first(
            tags,
            "WM/Composer",
        ),
        comment=_asf_first(
            tags,
            "Description",
            "WM/Comments",
        ),
        path=str(path),
    )


def _write_asf(
    path: Path,
    song: Song,
) -> None:
    audio = ASF(path)
    tags = audio.tags

    values = {
        "Title": song.title,
        "Author": song.artist,
        "WM/AlbumArtist": song.album_artist,
        "WM/AlbumTitle": song.album,
        "WM/Genre": song.genre,
        "WM/Year": song.year,
        "WM/TrackNumber": combine_number(
            song.track,
            song.total_tracks,
        ),
        "WM/PartOfSet": combine_number(
            song.disc,
            song.total_discs,
        ),
        "WM/ISRC": song.isrc,
        "WM/Publisher": song.label,
        "Copyright": song.copyright,
        "WM/Composer": song.composer,
        "Description": song.comment,
    }

    for key, value in values.items():
        value = str(
            value or ""
        ).strip()

        if value:
            tags[key] = [value]
        elif key in tags:
            del tags[key]

    audio.save()


def _write_wavpack_apev2(
    path: Path,
    song: Song,
) -> None:
    logger = get_diagnostic_logger(
        "wavpack"
    )

    try:
        tags = APEv2(path)
    except Exception:
        logger.exception(
            "Bestehende APEv2-Tags konnten nicht geladen werden: %s",
            path,
        )
        tags = APEv2()

    _write_apev2(
        tags,
        song,
    )

    try:
        tags.save(path)
    except Exception as error:
        logger.exception(
            "APEv2-Tags konnten nicht geschrieben werden: %s",
            path,
        )
        raise RuntimeError(
            "Die WavPack-Tags konnten nicht gespeichert werden. "
            "Details stehen in logs/wavpack.log."
        ) from error


def _read_apev2(
    path: Path,
    audio: WavPack,
) -> Song:
    tags = audio.tags or {}
    track, total_tracks = split_number(
        _ape_first(
            tags,
            "Track",
            "Tracknumber",
        )
    )
    disc, total_discs = split_number(
        _ape_first(
            tags,
            "Disc",
            "Discnumber",
        )
    )

    return Song(
        title=_ape_first(
            tags,
            "Title",
        ),
        artist=_ape_first(
            tags,
            "Artist",
        ),
        album_artist=_ape_first(
            tags,
            "Album Artist",
            "AlbumArtist",
            "Album_Artist",
        ),
        album=_ape_first(
            tags,
            "Album",
        ),
        genre=_ape_first(
            tags,
            "Genre",
        ),
        year=_ape_first(
            tags,
            "Year",
            "Date",
        ),
        track=track,
        total_tracks=total_tracks,
        disc=disc,
        total_discs=total_discs,
        isrc=_ape_first(
            tags,
            "ISRC",
        ),
        label=_ape_first(
            tags,
            "Label",
            "Publisher",
            "Organization",
        ),
        copyright=_ape_first(
            tags,
            "Copyright",
        ),
        composer=_ape_first(
            tags,
            "Composer",
        ),
        comment=_ape_first(
            tags,
            "Comment",
            "Commentary",
            "Description",
        ),
        path=str(path),
    )


def _write_apev2(
    tags: APEv2,
    song: Song,
) -> None:
    values = {
        "Title": song.title,
        "Artist": song.artist,
        "Album Artist": (
            song.album_artist
        ),
        "Album": song.album,
        "Genre": song.genre,
        "Year": song.year,
        "Track": combine_number(
            song.track,
            song.total_tracks,
        ),
        "Disc": combine_number(
            song.disc,
            song.total_discs,
        ),
        "ISRC": song.isrc,
        "Label": song.label,
        "Copyright": song.copyright,
        "Composer": song.composer,
        "Comment": song.comment,
    }

    aliases = {
        "Album Artist": (
            "AlbumArtist",
            "Album_Artist",
        ),
        "Track": (
            "Tracknumber",
        ),
        "Disc": (
            "Discnumber",
        ),
        "Year": (
            "Date",
        ),
    }

    for key, value in values.items():
        value = str(
            value or ""
        ).strip()

        for alias in aliases.get(
            key,
            (),
        ):
            if alias in tags:
                del tags[alias]

        if value:
            tags[key] = value
        elif key in tags:
            del tags[key]


def _read_mp3(
    path: Path,
) -> Song:
    audio = MP3(path)
    tags = audio.tags or ID3()

    def text(
        frame: str,
    ) -> str:
        item = tags.get(frame)

        return (
            str(item.text[0])
            if (
                item is not None
                and getattr(
                    item,
                    "text",
                    None,
                )
            )
            else ""
        )

    def txxx(
        desc: str,
    ) -> str:
        frames = tags.getall(
            "TXXX"
        )

        for frame in frames:
            if (
                frame.desc.casefold()
                == desc.casefold()
                and frame.text
            ):
                return str(
                    frame.text[0]
                )

        return ""

    track, total_tracks = split_number(
        text("TRCK")
    )
    disc, total_discs = split_number(
        text("TPOS")
    )
    comments = tags.getall(
        "COMM"
    )

    return Song(
        title=text("TIT2"),
        artist=text("TPE1"),
        album_artist=text("TPE2"),
        album=text("TALB"),
        genre=text("TCON"),
        year=text("TDRC"),
        track=track,
        total_tracks=total_tracks,
        disc=disc,
        total_discs=total_discs,
        isrc=text("TSRC"),
        label=(
            txxx("LABEL")
            or txxx("ORGANIZATION")
        ),
        copyright=text("TCOP"),
        composer=text("TCOM"),
        comment=(
            str(
                comments[0].text[0]
            )
            if (
                comments
                and comments[0].text
            )
            else ""
        ),
        path=str(path),
    )


def _write_mp3(
    path: Path,
    song: Song,
) -> None:
    # Hinweis: Kein separates MP3(path) mehr – der frühere Aufruf hat die
    # komplette Datei nur geparst, das Ergebnis aber verworfen. ID3(path)
    # liest die Tags direkt; das spart einen vollständigen Datei-Parse.
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    frames = {
        "TIT2": TIT2(
            encoding=3,
            text=[song.title],
        ),
        "TPE1": TPE1(
            encoding=3,
            text=[song.artist],
        ),
        "TPE2": TPE2(
            encoding=3,
            text=[song.album_artist],
        ),
        "TALB": TALB(
            encoding=3,
            text=[song.album],
        ),
        "TCON": TCON(
            encoding=3,
            text=[song.genre],
        ),
        "TDRC": TDRC(
            encoding=3,
            text=[song.year],
        ),
        "TRCK": TRCK(
            encoding=3,
            text=[
                combine_number(
                    song.track,
                    song.total_tracks,
                )
            ],
        ),
        "TPOS": TPOS(
            encoding=3,
            text=[
                combine_number(
                    song.disc,
                    song.total_discs,
                )
            ],
        ),
        "TSRC": TSRC(
            encoding=3,
            text=[song.isrc],
        ),
        "TCOP": TCOP(
            encoding=3,
            text=[song.copyright],
        ),
        "TCOM": TCOM(
            encoding=3,
            text=[song.composer],
        ),
    }

    for frame_id, frame in (
        frames.items()
    ):
        tags.delall(frame_id)

        if (
            frame.text
            and str(
                frame.text[0]
            ).strip()
        ):
            tags.add(frame)

    tags.delall("TXXX:LABEL")

    if song.label.strip():
        tags.add(
            TXXX(
                encoding=3,
                desc="LABEL",
                text=[song.label],
            )
        )

    tags.delall("COMM")

    if song.comment.strip():
        tags.add(
            COMM(
                encoding=3,
                lang="deu",
                desc="",
                text=[song.comment],
            )
        )

    tags.save(
        path,
        v2_version=3,
    )


def _read_mp4(
    path: Path,
) -> Song:
    audio = MP4(path)
    tags = audio.tags or {}

    def val(
        key,
    ):
        item = tags.get(key)

        if not item:
            return ""

        value = item[0]

        if isinstance(
            value,
            bytes,
        ):
            return value.decode(
                "utf-8",
                errors="replace",
            )

        return str(value)

    track_pair = (
        tags.get("trkn")
        or [(0, 0)]
    )[0]
    disc_pair = (
        tags.get("disk")
        or [(0, 0)]
    )[0]

    return Song(
        title=val("\xa9nam"),
        artist=val("\xa9ART"),
        album_artist=val("aART"),
        album=val("\xa9alb"),
        genre=val("\xa9gen"),
        year=val("\xa9day"),
        track=str(
            track_pair[0]
            or ""
        ),
        total_tracks=str(
            track_pair[1]
            or ""
        ),
        disc=str(
            disc_pair[0]
            or ""
        ),
        total_discs=str(
            disc_pair[1]
            or ""
        ),
        isrc=val(
            "----:com.apple.iTunes:ISRC"
        ),
        label=val(
            "----:com.apple.iTunes:LABEL"
        ),
        copyright=val("cprt"),
        composer=val("\xa9wrt"),
        comment=val("\xa9cmt"),
        path=str(path),
    )


def _write_mp4(
    path: Path,
    song: Song,
) -> None:
    audio = MP4(path)

    if audio.tags is None:
        audio.add_tags()

    tags = audio.tags
    simple = {
        "\xa9nam": song.title,
        "\xa9ART": song.artist,
        "aART": song.album_artist,
        "\xa9alb": song.album,
        "\xa9gen": song.genre,
        "\xa9day": song.year,
        "cprt": song.copyright,
        "\xa9wrt": song.composer,
        "\xa9cmt": song.comment,
    }

    for key, value in simple.items():
        if str(
            value or ""
        ).strip():
            tags[key] = [str(value)]
        elif key in tags:
            del tags[key]

    tags["trkn"] = [
        (
            int(
                song.track
                or 0
            ),
            int(
                song.total_tracks
                or 0
            ),
        )
    ]
    tags["disk"] = [
        (
            int(
                song.disc
                or 0
            ),
            int(
                song.total_discs
                or 0
            ),
        )
    ]

    for key, value in (
        (
            "----:com.apple.iTunes:ISRC",
            song.isrc,
        ),
        (
            "----:com.apple.iTunes:LABEL",
            song.label,
        ),
    ):
        if str(
            value or ""
        ).strip():
            tags[key] = [
                str(value).encode(
                    "utf-8"
                )
            ]
        elif key in tags:
            del tags[key]

    audio.save()
