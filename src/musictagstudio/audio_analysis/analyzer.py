from __future__ import annotations

import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

from .models import (
    AudioAnalysisResult,
    FFmpegInstallation,
)


REPLAYGAIN_REFERENCE_LUFS = -18.0


class AudioAnalysisError(
    RuntimeError
):
    """Eine Audiodatei konnte nicht analysiert werden."""


def analyze_file(
    filepath: str | Path,
    installation: FFmpegInstallation,
) -> AudioAnalysisResult:
    path = Path(filepath)

    try:
        probe_payload = _probe_file(
            path,
            installation,
        )
        loudness_payload = _measure_loudness(
            path,
            installation,
        )
    except AudioAnalysisError as error:
        return AudioAnalysisResult(
            path=str(path),
            file_size=(
                path.stat().st_size
                if path.is_file()
                else 0
            ),
            error=str(error),
        )

    result = parse_probe_payload(
        str(path),
        probe_payload,
    )
    loudness = parse_loudnorm_output(
        loudness_payload
    )

    integrated_lufs = loudness.get(
        "input_i"
    )
    true_peak_db = loudness.get(
        "input_tp"
    )
    loudness_range = loudness.get(
        "input_lra"
    )
    threshold = loudness.get(
        "input_thresh"
    )

    track_gain = calculate_replaygain(
        integrated_lufs
    )
    track_peak = db_to_linear(
        true_peak_db
    )

    return AudioAnalysisResult(
        **{
            **result.__dict__,
            "integrated_lufs": integrated_lufs,
            "loudness_range_lu": loudness_range,
            "true_peak_db": true_peak_db,
            "threshold_lufs": threshold,
            "replaygain_track_gain_db": track_gain,
            "replaygain_track_peak": track_peak,
            "peak_status": classify_true_peak(
                true_peak_db
            ),
        }
    )


def analyze_album_loudness(
    filepaths: list[str],
    installation: FFmpegInstallation,
) -> tuple[
    float | None,
    float | None,
]:
    existing_paths = [
        Path(filepath)
        for filepath in filepaths
        if Path(filepath).is_file()
    ]

    if not existing_paths:
        return None, None

    list_file_path = ""

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            encoding="utf-8",
            delete=False,
        ) as list_file:
            list_file_path = (
                list_file.name
            )

            for path in existing_paths:
                escaped = str(
                    path.resolve()
                ).replace(
                    "'",
                    "'\\''",
                )
                list_file.write(
                    f"file '{escaped}'\n"
                )

        command = [
            installation.ffmpeg_path,
            "-hide_banner",
            "-nostats",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file_path,
            "-vn",
            "-af",
            (
                "loudnorm="
                "I=-18:TP=-1:LRA=11:"
                "print_format=json"
            ),
            "-f",
            "null",
            "-",
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(
                120,
                len(existing_paths) * 45,
            ),
            creationflags=_creation_flags(),
        )

        payload = parse_loudnorm_output(
            completed.stderr
        )
        integrated = payload.get(
            "input_i"
        )
        true_peak = payload.get(
            "input_tp"
        )

        return (
            calculate_replaygain(
                integrated
            ),
            db_to_linear(
                true_peak
            ),
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return None, None
    finally:
        if list_file_path:
            try:
                Path(
                    list_file_path
                ).unlink(
                    missing_ok=True
                )
            except OSError:
                pass


def parse_probe_payload(
    filepath: str,
    payload: dict,
) -> AudioAnalysisResult:
    format_info = payload.get(
        "format",
        {}
    )
    streams = payload.get(
        "streams",
        []
    )
    audio_stream = next(
        (
            stream
            for stream in streams
            if stream.get(
                "codec_type"
            ) == "audio"
        ),
        {},
    )

    sample_rate = _as_int(
        audio_stream.get(
            "sample_rate"
        )
    )
    bitrate = _as_int(
        audio_stream.get(
            "bit_rate"
        )
        or format_info.get(
            "bit_rate"
        )
    )
    duration = _as_float(
        audio_stream.get(
            "duration"
        )
        or format_info.get(
            "duration"
        )
    )
    bit_depth = _as_int(
        audio_stream.get(
            "bits_per_raw_sample"
        )
        or audio_stream.get(
            "bits_per_sample"
        )
    )

    return AudioAnalysisResult(
        path=filepath,
        codec=str(
            audio_stream.get(
                "codec_name",
                "",
            )
        ),
        container=str(
            format_info.get(
                "format_name",
                "",
            )
        ),
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        channels=_as_int(
            audio_stream.get(
                "channels"
            )
        ),
        channel_layout=str(
            audio_stream.get(
                "channel_layout",
                "",
            )
        ),
        bitrate=bitrate,
        duration_seconds=duration,
        file_size=_as_int(
            format_info.get(
                "size"
            )
        ),
    )


def parse_loudnorm_output(
    stderr_text: str,
) -> dict[str, float]:
    json_blocks = re.findall(
        r"\{\s*"
        r'"input_i".*?'
        r"\}",
        stderr_text,
        flags=re.DOTALL,
    )

    if not json_blocks:
        return {}

    try:
        raw = json.loads(
            json_blocks[-1]
        )
    except json.JSONDecodeError:
        return {}

    result: dict[str, float] = {}

    for name in (
        "input_i",
        "input_tp",
        "input_lra",
        "input_thresh",
    ):
        value = _as_optional_float(
            raw.get(name)
        )

        if value is not None:
            result[name] = value

    return result



def classify_true_peak(
    true_peak_db: float | None,
) -> str:
    """
    Vorsichtige, alltagstaugliche Einordnung des gemessenen True Peak.

    Bis einschließlich 1 dBTP wird kein Warnstatus angezeigt. Werte über
    1 bis einschließlich 2 dBTP erhalten einen Hinweis. Erst über 2 dBTP
    wird der Wert als kritisch markiert. Die Einordnung ist ein Hinweis
    und kein zweifelsfreier Nachweis für hörbares Clipping.
    """
    if true_peak_db is None:
        return "unknown"

    if true_peak_db > 2.0:
        return "critical"

    if true_peak_db > 1.0:
        return "elevated"

    return "normal"

def calculate_replaygain(
    integrated_lufs: float | None,
) -> float | None:
    if integrated_lufs is None:
        return None

    return (
        REPLAYGAIN_REFERENCE_LUFS
        - integrated_lufs
    )


def db_to_linear(
    db_value: float | None,
) -> float | None:
    if db_value is None:
        return None

    return math.pow(
        10.0,
        db_value / 20.0,
    )


def _probe_file(
    path: Path,
    installation: FFmpegInstallation,
) -> dict:
    command = [
        installation.ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        (
            "format=format_name,duration,"
            "size,bit_rate:"
            "stream=codec_type,codec_name,"
            "sample_rate,bits_per_sample,"
            "bits_per_raw_sample,channels,"
            "channel_layout,bit_rate,duration"
        ),
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
            creationflags=_creation_flags(),
        )
    except (
        OSError,
        subprocess.SubprocessError,
    ) as error:
        raise AudioAnalysisError(
            f"ffprobe konnte nicht ausgeführt werden: {error}"
        ) from error

    if completed.returncode != 0:
        raise AudioAnalysisError(
            completed.stderr.strip()
            or "ffprobe meldete einen Fehler."
        )

    try:
        return json.loads(
            completed.stdout
        )
    except json.JSONDecodeError as error:
        raise AudioAnalysisError(
            "Die ffprobe-Ausgabe war kein gültiges JSON."
        ) from error


def _measure_loudness(
    path: Path,
    installation: FFmpegInstallation,
) -> str:
    command = [
        installation.ffmpeg_path,
        "-hide_banner",
        "-nostats",
        "-i",
        str(path),
        "-vn",
        "-af",
        (
            "loudnorm="
            "I=-18:TP=-1:LRA=11:"
            "print_format=json"
        ),
        "-f",
        "null",
        "-",
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
        raise AudioAnalysisError(
            f"FFmpeg konnte nicht ausgeführt werden: {error}"
        ) from error

    if completed.returncode != 0:
        raise AudioAnalysisError(
            completed.stderr.strip()
            or "FFmpeg meldete einen Fehler."
        )

    return completed.stderr


def _as_int(
    value: object,
) -> int:
    try:
        return int(float(value))
    except (
        TypeError,
        ValueError,
    ):
        return 0


def _as_float(
    value: object,
) -> float:
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def _as_optional_float(
    value: object,
) -> float | None:
    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(number):
        return None

    return number


def _creation_flags() -> int:
    return int(
        getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )
    )
