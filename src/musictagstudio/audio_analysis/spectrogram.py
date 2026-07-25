from __future__ import annotations

import subprocess
from hashlib import sha1
from pathlib import Path

from .cache import default_cache_path, file_fingerprint
from .models import FFmpegInstallation


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
    installation: FFmpegInstallation,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    use_cache: bool = True,
) -> Path:
    """
    Erzeugt ein Spektrogramm-PNG (Zeit-/Frequenzverlauf, Farbe = Pegel).

    Nutzt den bereits ausgelieferten FFmpeg-Filter ``showspectrumpic``.
    Unveränderte Dateien werden aus dem lokalen Cache geliefert.
    """
    path = Path(filepath)

    if not path.is_file():
        raise SpectrogramError(
            f"Datei nicht gefunden: {path}"
        )

    if not installation.available:
        raise SpectrogramError(
            "FFmpeg ist nicht verfügbar."
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

    command = [
        installation.ffmpeg_path,
        "-hide_banner",
        "-nostats",
        "-y",
        "-i",
        str(path),
        "-lavfi",
        (
            f"showspectrumpic=s={width}x{height}:"
            "legend=1:fscale=lin:color=intensity:scale=log"
        ),
        "-frames:v",
        "1",
        str(output_path),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            creationflags=_creation_flags(),
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ) as error:
        raise SpectrogramError(
            f"FFmpeg konnte nicht ausgeführt werden: {error}"
        ) from error

    if (
        completed.returncode != 0
        or not output_path.is_file()
    ):
        raise SpectrogramError(
            completed.stderr.strip()
            or "FFmpeg meldete einen Fehler."
        )

    return output_path


def _creation_flags() -> int:
    return int(
        getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )
    )
