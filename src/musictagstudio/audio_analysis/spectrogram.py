from __future__ import annotations

from hashlib import sha1
from pathlib import Path

from . import av_backend
from .cache import default_cache_path, file_fingerprint


DEFAULT_WIDTH = 960
DEFAULT_HEIGHT = 480


class SpectrogramError(RuntimeError):
    """Ein Spektrogramm konnte nicht erzeugt werden."""


def spectrogram_cache_path(
    path: Path,
    *,
    width: int,
    height: int,
) -> Path:
    """Stabiler Cache-Ort je Datei, Fingerabdruck und Bildgröße."""
    fingerprint = file_fingerprint(path)
    signature = (
        f"{str(path.resolve()).casefold()}|"
        f"{fingerprint['size']}|{fingerprint['mtime_ns']}|"
        f"{width}x{height}"
    )
    digest = sha1(signature.encode("utf-8")).hexdigest()
    return (
        default_cache_path().parent
        / "spectrograms"
        / f"{digest}.png"
    )


def render_spectrogram(
    filepath: str | Path,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    use_cache: bool = True,
) -> Path:
    """
    Erzeugt ein Spektrogramm-PNG (Zeit-/Frequenzverlauf, Farbe = Pegel).

    Nutzt den FFmpeg-Filter ``showspectrumpic`` über PyAV (gebündeltes FFmpeg).
    Unveränderte Dateien werden aus dem lokalen Cache geliefert.
    """
    path = Path(filepath)

    if not path.is_file():
        raise SpectrogramError(
            f"Datei nicht gefunden: {path}"
        )

    output_path = spectrogram_cache_path(
        path,
        width=width,
        height=height,
    )

    if use_cache and output_path.is_file():
        return output_path

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        av_backend.render_spectrogram_png(
            str(path),
            str(output_path),
            width=width,
            height=height,
        )
    except Exception as error:  # PyAV/Container-Fehler
        raise SpectrogramError(
            f"Spektrogramm konnte nicht erzeugt werden: {error}"
        ) from error

    if not output_path.is_file():
        raise SpectrogramError("Spektrogramm konnte nicht erzeugt werden.")

    return output_path
