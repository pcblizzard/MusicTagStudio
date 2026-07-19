from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile

from mutagen.apev2 import APEv2, error as APEv2Error
from mutagen.asf import ASF
from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3NoHeaderError, SYLT, USLT
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from .embedded import read_embedded_lyrics_variants
from .lrc import render_lrc
from .models import LyricsDocument


@dataclass(frozen=True)
class LyricsEmbeddingPlan:
    audio_path: str
    format_name: str
    supported: bool
    preserves_sync: bool
    existing: tuple[LyricsDocument, ...] = ()
    warning: str = ""

    @property
    def replaces_existing(self) -> bool:
        return bool(self.existing)


_FORMATS = {
    ".mp3": ("MP3 / ID3", True),
    ".flac": ("FLAC / Vorbis Comments", True),
    ".ogg": ("Ogg Vorbis", True),
    ".oga": ("Ogg Vorbis", True),
    ".opus": ("Opus", True),
    ".wv": ("WavPack / APEv2", True),
    ".ape": ("Monkey's Audio / APEv2", True),
    ".m4a": ("M4A / MP4", False),
    ".m4b": ("M4B / MP4", False),
    ".mp4": ("MP4", False),
    ".wma": ("WMA / ASF", False),
    ".asf": ("ASF", False),
}


def build_embedding_plan(
    audio_path: str | Path,
    document: LyricsDocument,
) -> LyricsEmbeddingPlan:
    path = Path(audio_path)
    format_info = _FORMATS.get(path.suffix.casefold())
    if format_info is None:
        return LyricsEmbeddingPlan(
            str(path),
            path.suffix.upper().lstrip(".") or "Unbekannt",
            False,
            False,
            warning="Dieses Audioformat unterstützt MusicTagStudio noch nicht.",
        )
    format_name, preserves_sync = format_info
    existing = read_embedded_lyrics_variants(path)
    warning = ""
    if document.is_synced and not preserves_sync:
        warning = (
            "Dieses Format besitzt hier kein zuverlässig unterstütztes Feld für "
            "synchronisierte Lyrics. Es wird nur der Klartext eingebettet; die "
            "LRC-Datei behält ihre Zeitmarken."
        )
    return LyricsEmbeddingPlan(
        str(path),
        format_name,
        True,
        preserves_sync,
        existing,
        warning,
    )


def embed_lyrics(
    audio_path: str | Path,
    document: LyricsDocument,
    *,
    confirmed: bool = False,
) -> LyricsEmbeddingPlan:
    if not confirmed:
        raise PermissionError("Lyrics dürfen nur nach bestätigter Vorschau eingebettet werden.")
    if document.is_empty:
        raise ValueError("Leere Lyrics werden nicht eingebettet.")
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audiodatei nicht gefunden: {path}")
    plan = build_embedding_plan(path, document)
    if not plan.supported:
        raise ValueError(plan.warning)

    backup: Path | None = None
    try:
        with NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.lyrics-backup-",
            suffix=path.suffix,
            delete=False,
        ) as handle:
            backup = Path(handle.name)
        shutil.copy2(path, backup)
        _write_for_suffix(path, document)
    except Exception:
        if backup is not None and backup.is_file():
            shutil.copy2(backup, path)
        raise
    finally:
        if backup is not None:
            backup.unlink(missing_ok=True)
    return plan


def _write_for_suffix(path: Path, document: LyricsDocument) -> None:
    suffix = path.suffix.casefold()
    if suffix == ".mp3":
        _write_id3(path, document)
    elif suffix == ".flac":
        _write_vorbis(FLAC(path), document)
    elif suffix in {".ogg", ".oga"}:
        _write_vorbis(OggVorbis(path), document)
    elif suffix == ".opus":
        _write_vorbis(OggOpus(path), document)
    elif suffix in {".wv", ".ape"}:
        _write_apev2(path, document)
    elif suffix in {".m4a", ".m4b", ".mp4"}:
        _write_mp4(path, document)
    elif suffix in {".wma", ".asf"}:
        _write_asf(path, document)
    else:
        raise ValueError(f"Nicht unterstütztes Audioformat: {suffix}")


def _write_id3(path: Path, document: LyricsDocument) -> None:
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("USLT")
    tags.delall("SYLT")
    tags.add(USLT(encoding=3, lang="und", desc="", text=document.display_text()))
    if document.synced_lines:
        tags.add(
            SYLT(
                encoding=3,
                lang="und",
                format=2,
                type=1,
                desc="",
                text=[(line.text, line.time_ms) for line in document.synced_lines],
            )
        )
    tags.save(path, v2_version=3)


def _write_vorbis(audio, document: LyricsDocument) -> None:
    audio["LYRICS"] = [document.display_text()]
    if document.synced_lines:
        audio["SYNCEDLYRICS"] = [render_lrc(document).rstrip("\n")]
    elif "SYNCEDLYRICS" in audio:
        del audio["SYNCEDLYRICS"]
    audio.save()


def _write_apev2(path: Path, document: LyricsDocument) -> None:
    try:
        tags = APEv2(path)
    except (APEv2Error, OSError):
        tags = APEv2()
    tags["Lyrics"] = document.display_text()
    if document.synced_lines:
        tags["SyncedLyrics"] = render_lrc(document).rstrip("\n")
    elif "SyncedLyrics" in tags:
        del tags["SyncedLyrics"]
    tags.save(path)


def _write_mp4(path: Path, document: LyricsDocument) -> None:
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()
    audio.tags["\xa9lyr"] = [document.display_text()]
    audio.save()


def _write_asf(path: Path, document: LyricsDocument) -> None:
    audio = ASF(path)
    audio.tags["WM/Lyrics"] = [document.display_text()]
    audio.save()
