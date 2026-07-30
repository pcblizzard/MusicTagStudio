"""Schnelle, verlässliche Audioqualität aus den lokalen Dateien (via mutagen).

Liest Codec, Abtastrate, Bit-Tiefe, Kanäle und Bitrate direkt aus den
Datei-Headern – ohne ffprobe/ffmpeg, damit es auch im gebündelten Build ohne
externe Werkzeuge funktioniert. Bewusst getrennt von der schweren
Loudness-Analyse in :mod:`analyzer` (die ffmpeg braucht).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from mutagen import File as MutagenFile

# mutagen-Klassenname -> (Anzeige-Codec, verlustfrei?)
_CODEC_BY_CLASS: dict[str, tuple[str, bool]] = {
    "FLAC": ("FLAC", True),
    "WAVE": ("WAV", True),
    "AIFF": ("AIFF", True),
    "WavPack": ("WavPack", True),
    "MonkeysAudio": ("Monkey's Audio", True),
    "TAK": ("TAK", True),
    "OptimFROG": ("OptimFROG", True),
    "TrueAudio": ("TrueAudio", True),
    "OggFLAC": ("FLAC", True),
    "MP3": ("MP3", False),
    "OggVorbis": ("Vorbis", False),
    "OggOpus": ("Opus", False),
    "OggSpeex": ("Speex", False),
    "Musepack": ("Musepack", False),
}


@dataclass(frozen=True)
class TrackQuality:
    path: str
    codec: str = ""
    sample_rate: int = 0
    bit_depth: int = 0
    channels: int = 0
    bitrate: int = 0
    lossless: bool = False
    error: str = ""

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def sample_rate_text(self) -> str:
        return f"{self.sample_rate / 1000:.1f} kHz" if self.sample_rate else ""

    @property
    def bit_depth_text(self) -> str:
        return f"{self.bit_depth} Bit" if self.bit_depth else ""

    @property
    def bitrate_text(self) -> str:
        return f"{round(self.bitrate / 1000)} kbit/s" if self.bitrate else ""

    @property
    def channels_text(self) -> str:
        if self.channels == 1:
            return "Mono"
        if self.channels == 2:
            return "Stereo"
        return f"{self.channels} Kanäle" if self.channels else ""

    @property
    def technical_signature(self) -> tuple[object, ...]:
        return (self.codec.casefold(), self.sample_rate, self.bit_depth, self.channels)

    def summary(self) -> str:
        """Kompakte Einzeilen-Beschreibung, z. B. 'FLAC · 16 Bit · 44.1 kHz · Stereo'.

        Reihenfolge bewusst **Format · Bit-Tiefe · Abtastrate** – gleich wie die
        TIDAL-Qualität (Tier-Label „… 16 Bit/44.1 kHz" bzw. exakte tidalapi-
        Werte), damit beide Zeilen direkt vergleichbar sind.
        """
        if self.error:
            return self.error
        # Verlustfrei: Bit-Tiefe betonen (vor der Rate); verlustbehaftet: Bitrate.
        parts = [self.codec or "?"]
        if self.lossless and self.bit_depth_text:
            parts.append(self.bit_depth_text)
        if self.sample_rate_text:
            parts.append(self.sample_rate_text)
        if not self.lossless and self.bitrate_text:
            parts.append(self.bitrate_text)
        if self.channels_text:
            parts.append(self.channels_text)
        return " · ".join(parts)


def probe_quality(path: str | Path) -> TrackQuality:
    """Liest die technische Qualität einer einzelnen Datei (mutagen)."""
    text = str(path)
    file_path = Path(text)
    if not file_path.is_file():
        return TrackQuality(path=text, error="Datei nicht gefunden")
    try:
        audio = MutagenFile(text)
    except Exception:
        return TrackQuality(path=text, error="Datei nicht lesbar")
    info = getattr(audio, "info", None)
    if audio is None or info is None:
        return TrackQuality(path=text, error="Unbekanntes Format")

    codec, lossless = _codec_and_lossless(type(audio).__name__, info, file_path)
    sample_rate = _as_int(getattr(info, "sample_rate", 0))
    channels = _as_int(getattr(info, "channels", 0))
    bitrate = _as_int(getattr(info, "bitrate", 0))
    # Bit-Tiefe nur bei verlustfreien Formaten sinnvoll; verlustbehaftete haben
    # keine (mutagen liefert sie dort ohnehin nicht).
    bit_depth = _as_int(getattr(info, "bits_per_sample", 0)) if lossless else 0
    return TrackQuality(
        path=text,
        codec=codec,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        channels=channels,
        bitrate=bitrate,
        lossless=lossless,
    )


def _codec_and_lossless(class_name: str, info: object, path: Path) -> tuple[str, bool]:
    if class_name == "MP4":
        # m4a kann ALAC (verlustfrei) oder AAC (verlustbehaftet) sein.
        codec_id = str(getattr(info, "codec", "") or "").lower()
        if "alac" in codec_id or _as_int(getattr(info, "bits_per_sample", 0)) > 0:
            return "ALAC", True
        return "AAC", False
    mapped = _CODEC_BY_CLASS.get(class_name)
    if mapped is not None:
        return mapped
    # Unbekannte mutagen-Klasse: nach Endung raten, konservativ verlustbehaftet.
    return path.suffix.lstrip(".").upper() or class_name, False


def _as_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class AlbumQuality:
    tracks: tuple[TrackQuality, ...]

    @property
    def analyzed(self) -> tuple[TrackQuality, ...]:
        return tuple(track for track in self.tracks if track.ok)

    @property
    def failed(self) -> tuple[TrackQuality, ...]:
        return tuple(track for track in self.tracks if not track.ok)

    @property
    def dominant_signature(self) -> tuple[object, ...] | None:
        analyzed = self.analyzed
        if not analyzed:
            return None
        counts = Counter(track.technical_signature for track in analyzed)
        return counts.most_common(1)[0][0]

    @property
    def is_mixed(self) -> bool:
        return len({track.technical_signature for track in self.analyzed}) > 1

    @property
    def all_lossless(self) -> bool:
        analyzed = self.analyzed
        return bool(analyzed) and all(track.lossless for track in analyzed)

    def summary(self) -> str:
        """Album-Kurzfassung anhand des häufigsten Formats (+ Hinweis bei Mix)."""
        analyzed = self.analyzed
        if not analyzed:
            return "Keine lesbaren Audiodateien"
        signature = self.dominant_signature
        representative = next(
            track for track in analyzed if track.technical_signature == signature
        )
        text = representative.summary()
        if self.is_mixed:
            text += " · gemischt"
        return text


def summarize_album(paths: list[str] | tuple[str, ...]) -> AlbumQuality:
    """Liest die Qualität aller angegebenen Dateien und fasst sie zusammen."""
    return AlbumQuality(tracks=tuple(probe_quality(path) for path in paths))
