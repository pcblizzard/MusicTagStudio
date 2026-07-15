from __future__ import annotations

from pathlib import Path

from mutagen.flac import FLAC
from mutagen.id3 import (
    ID3,
    ID3NoHeaderError,
    TXXX,
)
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wavpack import WavPack

from .models import AudioAnalysisResult


REPLAYGAIN_KEYS = {
    "track_gain": "REPLAYGAIN_TRACK_GAIN",
    "track_peak": "REPLAYGAIN_TRACK_PEAK",
    "album_gain": "REPLAYGAIN_ALBUM_GAIN",
    "album_peak": "REPLAYGAIN_ALBUM_PEAK",
}


def write_replaygain_tags(
    result: AudioAnalysisResult,
    *,
    overwrite: bool = False,
) -> None:
    path = Path(result.path)
    suffix = path.suffix.casefold()
    values = replaygain_values(result)

    if suffix == ".flac":
        audio = FLAC(path)
        _write_vorbis(
            audio,
            values,
            overwrite=overwrite,
        )
        audio.save()
        return

    if suffix == ".wv":
        audio = WavPack(path)

        if audio.tags is None:
            audio.add_tags()

        _write_apev2(
            audio.tags,
            values,
            overwrite=overwrite,
        )
        audio.save()
        return

    if suffix in {".ogg", ".oga"}:
        audio = OggVorbis(path)
        _write_vorbis(
            audio,
            values,
            overwrite=overwrite,
        )
        audio.save()
        return

    if suffix == ".opus":
        audio = OggOpus(path)
        _write_vorbis(
            audio,
            values,
            overwrite=overwrite,
        )
        audio.save()
        return

    if suffix == ".mp3":
        _write_mp3(
            path,
            values,
            overwrite=overwrite,
        )
        return

    if suffix in {".m4a", ".mp4"}:
        _write_mp4(
            path,
            values,
            overwrite=overwrite,
        )
        return

    raise ValueError(
        f"ReplayGain wird für {suffix} "
        "noch nicht unterstützt."
    )


def replaygain_values(
    result: AudioAnalysisResult,
) -> dict[str, str]:
    values: dict[str, str] = {}

    if (
        result.replaygain_track_gain_db
        is not None
    ):
        values[
            REPLAYGAIN_KEYS["track_gain"]
        ] = (
            f"{result.replaygain_track_gain_db:+.2f} dB"
        )

    if (
        result.replaygain_track_peak
        is not None
    ):
        values[
            REPLAYGAIN_KEYS["track_peak"]
        ] = (
            f"{result.replaygain_track_peak:.8f}"
        )

    if (
        result.replaygain_album_gain_db
        is not None
    ):
        values[
            REPLAYGAIN_KEYS["album_gain"]
        ] = (
            f"{result.replaygain_album_gain_db:+.2f} dB"
        )

    if (
        result.replaygain_album_peak
        is not None
    ):
        values[
            REPLAYGAIN_KEYS["album_peak"]
        ] = (
            f"{result.replaygain_album_peak:.8f}"
        )

    return values


def _write_vorbis(
    audio,
    values: dict[str, str],
    *,
    overwrite: bool,
) -> None:
    for key, value in values.items():
        existing = audio.get(key)

        if existing and not overwrite:
            continue

        audio[key] = [value]



def _write_apev2(
    tags,
    values: dict[str, str],
    *,
    overwrite: bool,
) -> None:
    for key, value in values.items():
        if (
            key in tags
            and not overwrite
        ):
            continue

        tags[key] = value


def _write_mp3(
    path: Path,
    values: dict[str, str],
    *,
    overwrite: bool,
) -> None:
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    for key, value in values.items():
        existing = [
            frame
            for frame in tags.getall("TXXX")
            if frame.desc.casefold()
            == key.casefold()
        ]

        if existing and not overwrite:
            continue

        for frame in existing:
            tags.delall(
                f"TXXX:{frame.desc}"
            )

        tags.add(
            TXXX(
                encoding=3,
                desc=key,
                text=[value],
            )
        )

    tags.save(
        path,
        v2_version=3,
    )


def _write_mp4(
    path: Path,
    values: dict[str, str],
    *,
    overwrite: bool,
) -> None:
    audio = MP4(path)

    if audio.tags is None:
        audio.add_tags()

    for key, value in values.items():
        atom = (
            "----:com.apple.iTunes:"
            + key
        )

        if (
            atom in audio.tags
            and not overwrite
        ):
            continue

        audio.tags[atom] = [
            value.encode("utf-8")
        ]

    audio.save()
