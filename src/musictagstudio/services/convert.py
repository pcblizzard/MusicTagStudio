"""Audio-Konvertierung über PyAV (gebündeltes FFmpeg) – ohne externe Tools.

Wandelt Titel z. B. von FLAC nach MP3/AAC/Opus (fürs Handy) oder ins
verlustfreie ALAC/FLAC. Erzeugt **neue** Dateien (nichts wird überschrieben)
und überträgt Tags und Cover so gut wie möglich.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConversionFormat:
    key: str
    label: str
    codec: str
    extension: str
    lossless: bool
    default_bitrate: int = 0  # nur relevant für verlustbehaftete Formate
    forced_rate: int = 0  # 0 = Quellrate behalten; sonst erzwingen (z. B. Opus)


# Auswahl der Zielformate (Encoder sind im gebündelten FFmpeg vorhanden).
# Opus unterstützt nur 48 kHz -> feste Abtastrate.
FORMATS: dict[str, ConversionFormat] = {
    "mp3": ConversionFormat("mp3", "MP3", "libmp3lame", ".mp3", False, 320000),
    "aac": ConversionFormat("aac", "AAC (M4A)", "aac", ".m4a", False, 256000),
    "opus": ConversionFormat(
        "opus", "Opus", "libopus", ".opus", False, 160000, forced_rate=48000
    ),
    "flac": ConversionFormat("flac", "FLAC", "flac", ".flac", True),
    "alac": ConversionFormat("alac", "ALAC (M4A)", "alac", ".m4a", True),
}

# Auswahlbare Bitraten (kbit/s) für verlustbehaftete Formate.
BITRATE_CHOICES = (128, 192, 256, 320)


class ConversionError(RuntimeError):
    """Eine Datei konnte nicht konvertiert werden."""


def target_path(source: str | Path, out_dir: str | Path, fmt: ConversionFormat) -> Path:
    """Zielpfad im Ausgabeordner mit passender Endung."""
    return Path(out_dir) / (Path(source).stem + fmt.extension)


def convert_file(
    source: str | Path,
    dest: str | Path,
    fmt: ConversionFormat,
    *,
    bitrate: int | None = None,
) -> None:
    """Konvertiert eine Datei in das Zielformat und überträgt Tags/Cover."""
    import av

    source = str(source)
    dest = str(dest)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)

    try:
        input_container = av.open(source)
    except Exception as error:  # noqa: BLE001
        raise ConversionError(f"Quelle nicht lesbar: {error}") from error

    try:
        streams = input_container.streams.audio
        if not streams:
            raise ConversionError("Keine Audiospur gefunden.")
        in_stream = streams[0]
        rate = fmt.forced_rate or int(in_stream.codec_context.sample_rate or 44100)

        output_container = av.open(dest, "w")
        out_stream = output_container.add_stream(fmt.codec, rate=rate)
        if not fmt.lossless:
            out_stream.bit_rate = int(
                bitrate if bitrate else fmt.default_bitrate
            )

        resampler = av.AudioResampler(
            format=out_stream.format,
            layout=out_stream.layout,
            rate=out_stream.rate,
        )

        try:
            for frame in input_container.decode(in_stream):
                frame.pts = None
                for resampled in resampler.resample(frame):
                    for packet in out_stream.encode(resampled):
                        output_container.mux(packet)
            for packet in out_stream.encode(None):
                output_container.mux(packet)
        finally:
            output_container.close()
    except ConversionError:
        raise
    except Exception as error:  # noqa: BLE001
        raise ConversionError(str(error)) from error
    finally:
        input_container.close()

    _copy_tags_and_cover(source, dest)


def _copy_tags_and_cover(source: str, dest: str) -> None:
    """Tags und Cover von der Quelle übernehmen (Best effort)."""
    try:
        from .metadata_io import read_metadata, save_song_metadata

        song = read_metadata(source)
        song.path = dest
        save_song_metadata(dest, song)
    except Exception:  # noqa: BLE001 - Tags sind optional
        pass

    try:
        from .cover import embed_cover, load_cover

        cover = load_cover(source)
        if cover:
            embed_cover(dest, cover)
    except Exception:  # noqa: BLE001 - Cover ist optional
        pass
