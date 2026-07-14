from __future__ import annotations

from pathlib import Path

from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3NoHeaderError, TCOM, TCON, TDRC, TIT2, TALB, TPE1, TPE2, TRCK, TPOS, TSRC, TCOP, COMM, TXXX
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from ..models.song import Song

SUPPORTED_AUDIO_EXTENSIONS = {
    ".flac", ".mp3", ".ogg", ".oga", ".opus", ".m4a", ".mp4"
}


def split_number(value: str) -> tuple[str, str]:
    value = str(value or "").strip()
    if "/" not in value:
        return value, ""
    number, total = value.split("/", 1)
    return number.strip(), total.strip()


def combine_number(number: str, total: str) -> str:
    number = str(number or "").strip()
    total = str(total or "").strip()
    if not number:
        return ""
    return f"{number}/{total}" if total else number


def read_metadata(filepath: str | Path) -> Song:
    path = Path(filepath)
    suffix = path.suffix.lower()
    if suffix == ".flac":
        return _read_vorbis(path, FLAC(path))
    if suffix in {".ogg", ".oga"}:
        return _read_vorbis(path, OggVorbis(path))
    if suffix == ".opus":
        return _read_vorbis(path, OggOpus(path))
    if suffix == ".mp3":
        return _read_mp3(path)
    if suffix in {".m4a", ".mp4"}:
        return _read_mp4(path)
    raise ValueError(f"Nicht unterstütztes Audioformat: {suffix}")


def save_song_metadata(filepath: str | Path, song: Song) -> None:
    path = Path(filepath)
    suffix = path.suffix.lower()
    if suffix == ".flac":
        audio = FLAC(path); _write_vorbis(audio, song); audio.save(); return
    if suffix in {".ogg", ".oga"}:
        audio = OggVorbis(path); _write_vorbis(audio, song); audio.save(); return
    if suffix == ".opus":
        audio = OggOpus(path); _write_vorbis(audio, song); audio.save(); return
    if suffix == ".mp3":
        _write_mp3(path, song); return
    if suffix in {".m4a", ".mp4"}:
        _write_mp4(path, song); return
    raise ValueError(f"Nicht unterstütztes Audioformat: {suffix}")


def _first(tags, *names: str) -> str:
    for name in names:
        values = tags.get(name)
        if values:
            value = values[0] if isinstance(values, list) else values
            return str(value)
    return ""


def _read_vorbis(path: Path, audio) -> Song:
    track, total_tracks = split_number(_first(audio, "tracknumber"))
    disc, total_discs = split_number(_first(audio, "discnumber"))
    return Song(
        title=_first(audio, "title"), artist=_first(audio, "artist"),
        album_artist=_first(audio, "albumartist", "album artist", "album_artist"),
        album=_first(audio, "album"), genre=_first(audio, "genre"), year=_first(audio, "date"),
        track=track, total_tracks=total_tracks, disc=disc, total_discs=total_discs,
        isrc=_first(audio, "isrc"), label=_first(audio, "organization", "label", "publisher"),
        copyright=_first(audio, "copyright"), composer=_first(audio, "composer"),
        comment=_first(audio, "comment"), path=str(path),
    )


def _write_vorbis(audio, song: Song) -> None:
    values = {
        "title": song.title, "artist": song.artist, "albumartist": song.album_artist,
        "album": song.album, "genre": song.genre, "date": song.year,
        "tracknumber": combine_number(song.track, song.total_tracks),
        "discnumber": combine_number(song.disc, song.total_discs),
        "isrc": song.isrc, "organization": song.label, "copyright": song.copyright,
        "composer": song.composer, "comment": song.comment,
    }
    for key, value in values.items():
        value = str(value or "").strip()
        if value: audio[key] = [value]
        elif key in audio: del audio[key]


def _read_mp3(path: Path) -> Song:
    audio = MP3(path)
    tags = audio.tags or ID3()
    def text(frame: str) -> str:
        item = tags.get(frame)
        return str(item.text[0]) if item is not None and getattr(item, "text", None) else ""
    def txxx(desc: str) -> str:
        frames = tags.getall("TXXX")
        for frame in frames:
            if frame.desc.casefold() == desc.casefold() and frame.text:
                return str(frame.text[0])
        return ""
    track,total_tracks=split_number(text("TRCK")); disc,total_discs=split_number(text("TPOS"))
    comments=tags.getall("COMM")
    return Song(title=text("TIT2"), artist=text("TPE1"), album_artist=text("TPE2"), album=text("TALB"),
        genre=text("TCON"), year=text("TDRC"), track=track,total_tracks=total_tracks,disc=disc,total_discs=total_discs,
        isrc=text("TSRC"), label=txxx("LABEL") or txxx("ORGANIZATION"), copyright=text("TCOP"), composer=text("TCOM"),
        comment=str(comments[0].text[0]) if comments and comments[0].text else "", path=str(path))


def _write_mp3(path: Path, song: Song) -> None:
    audio=MP3(path)
    try: tags=ID3(path)
    except ID3NoHeaderError: tags=ID3()
    frames = {
        "TIT2": TIT2(encoding=3,text=[song.title]), "TPE1": TPE1(encoding=3,text=[song.artist]),
        "TPE2": TPE2(encoding=3,text=[song.album_artist]), "TALB": TALB(encoding=3,text=[song.album]),
        "TCON": TCON(encoding=3,text=[song.genre]), "TDRC": TDRC(encoding=3,text=[song.year]),
        "TRCK": TRCK(encoding=3,text=[combine_number(song.track,song.total_tracks)]),
        "TPOS": TPOS(encoding=3,text=[combine_number(song.disc,song.total_discs)]),
        "TSRC": TSRC(encoding=3,text=[song.isrc]), "TCOP": TCOP(encoding=3,text=[song.copyright]),
        "TCOM": TCOM(encoding=3,text=[song.composer]),
    }
    for frame_id, frame in frames.items():
        tags.delall(frame_id)
        if frame.text and str(frame.text[0]).strip(): tags.add(frame)
    tags.delall("TXXX:LABEL")
    if song.label.strip(): tags.add(TXXX(encoding=3,desc="LABEL",text=[song.label]))
    tags.delall("COMM")
    if song.comment.strip(): tags.add(COMM(encoding=3,lang="deu",desc="",text=[song.comment]))
    tags.save(path, v2_version=3)


def _read_mp4(path: Path) -> Song:
    audio=MP4(path); tags=audio.tags or {}
    def val(key):
        item=tags.get(key)
        if not item: return ""
        value=item[0]
        return str(value)
    track_pair=(tags.get("trkn") or [(0,0)])[0]; disc_pair=(tags.get("disk") or [(0,0)])[0]
    return Song(title=val("\xa9nam"),artist=val("\xa9ART"),album_artist=val("aART"),album=val("\xa9alb"),genre=val("\xa9gen"),year=val("\xa9day"),
        track=str(track_pair[0] or ""),total_tracks=str(track_pair[1] or ""),disc=str(disc_pair[0] or ""),total_discs=str(disc_pair[1] or ""),
        isrc=val("----:com.apple.iTunes:ISRC"),label=val("----:com.apple.iTunes:LABEL"),copyright=val("cprt"),composer=val("\xa9wrt"),comment=val("\xa9cmt"),path=str(path))


def _write_mp4(path: Path, song: Song) -> None:
    audio=MP4(path)
    if audio.tags is None: audio.add_tags()
    tags=audio.tags
    simple={"\xa9nam":song.title,"\xa9ART":song.artist,"aART":song.album_artist,"\xa9alb":song.album,"\xa9gen":song.genre,"\xa9day":song.year,
            "cprt":song.copyright,"\xa9wrt":song.composer,"\xa9cmt":song.comment}
    for key,value in simple.items():
        if str(value or "").strip(): tags[key]=[str(value)]
        elif key in tags: del tags[key]
    tags["trkn"]=[(int(song.track or 0),int(song.total_tracks or 0))]
    tags["disk"]=[(int(song.disc or 0),int(song.total_discs or 0))]
    for key,value in (("----:com.apple.iTunes:ISRC",song.isrc),("----:com.apple.iTunes:LABEL",song.label)):
        if str(value or "").strip(): tags[key]=[str(value).encode("utf-8")]
        elif key in tags: del tags[key]
    audio.save()
