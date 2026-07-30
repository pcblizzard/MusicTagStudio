from __future__ import annotations

import json
import math
import re
from pathlib import Path

from . import av_backend, deep_metrics
from .models import AudioAnalysisResult


REPLAYGAIN_REFERENCE_LUFS = -18.0


class AudioAnalysisError(
    RuntimeError
):
    """Eine Audiodatei konnte nicht analysiert werden."""


def analyze_file(
    filepath: str | Path,
) -> AudioAnalysisResult:
    path = Path(filepath)
    file_size = path.stat().st_size if path.is_file() else 0

    try:
        info = av_backend.probe(str(path))
        # Loudness UND tiefe Sample-Metriken in EINEM Dekodier-Durchlauf.
        deep, loud_raw = deep_metrics.analyze_full(str(path))
        loudness = _convert_loudness(loud_raw)
    except Exception as error:  # PyAV/Container-Fehler
        return AudioAnalysisResult(
            path=str(path),
            file_size=file_size,
            error=str(error) or "Datei konnte nicht analysiert werden.",
        )

    if not info:
        return AudioAnalysisResult(
            path=str(path),
            file_size=file_size,
            error="Keine Audiospur gefunden.",
        )

    integrated_lufs = loudness.get("input_i")
    true_peak_db = loudness.get("input_tp")
    loudness_range = loudness.get("input_lra")
    threshold = loudness.get("input_thresh")

    return AudioAnalysisResult(
        path=str(path),
        codec=info["codec"],
        container=info["container"],
        sample_rate=info["sample_rate"],
        bit_depth=info["bit_depth"],
        channels=info["channels"],
        channel_layout="",
        bitrate=info["bitrate"],
        duration_seconds=info["duration_seconds"],
        file_size=file_size,
        integrated_lufs=integrated_lufs,
        loudness_range_lu=loudness_range,
        true_peak_db=true_peak_db,
        threshold_lufs=threshold,
        replaygain_track_gain_db=calculate_replaygain(integrated_lufs),
        replaygain_track_peak=db_to_linear(true_peak_db),
        peak_status=classify_true_peak(true_peak_db),
        decoded_format=deep.decoded_format,
        sample_count=deep.sample_count,
        peak_dbfs=deep.peak_dbfs,
        rms_dbfs=deep.rms_dbfs,
        dynamic_range_db=deep.dynamic_range_db,
        clipped_samples=deep.clipped_samples,
        spectral_cutoff_hz=deep.spectral_cutoff_hz,
        spectral_shelf_db=deep.spectral_shelf_db,
        spectral_steepness_db=deep.spectral_steepness_db,
        channel_peaks_dbfs=tuple(c.peak_dbfs for c in deep.channels),
        channel_rms_dbfs=tuple(c.rms_dbfs for c in deep.channels),
        channel_dynamic_range_db=tuple(c.dynamic_range_db for c in deep.channels),
        channel_clipped_samples=tuple(c.clipped_samples for c in deep.channels),
    )


def _convert_loudness(raw: dict) -> dict[str, float]:
    """Rohes loudnorm-JSON in ein float-Dict (input_i/tp/lra/thresh) wandeln."""
    result: dict[str, float] = {}
    for name in ("input_i", "input_tp", "input_lra", "input_thresh"):
        value = _as_optional_float(raw.get(name))
        if value is not None:
            result[name] = value
    return result


def _extract_loudness(paths: list[str]) -> dict[str, float]:
    """loudnorm-Messwerte als float-Dict (input_i/tp/lra/thresh)."""
    return _convert_loudness(av_backend.measure_loudness_json(paths))


def album_gain_peak_from_results(
    results: list[AudioAnalysisResult],
) -> tuple[float | None, float | None]:
    """Album Gain/Peak schnell aus den bereits gemessenen Track-Werten ableiten.

    Ohne zweiten Dekodier-Durchlauf:

    - **Album Peak** = Maximum der Track-True-Peaks → exakt (der Spitzenwert des
      Albums ist der höchste Track-Spitzenwert).
    - **Album Gain** = ``-18 LUFS − Album-Lautheit``, wobei die Album-Lautheit
      energie- und dauergewichtet aus den Track-LUFS gebildet wird (üblicher
      ReplayGain-2.0-Weg, sehr nahe am exakten „ganzes Album am Stück"-Wert).
    """
    usable = [
        result
        for result in results
        if not result.error and result.integrated_lufs is not None
    ]
    if not usable:
        return None, None

    # Energie (mittleres Quadrat) je Track, gewichtet mit der Dauer.
    weighted_energy = 0.0
    total_duration = 0.0
    for result in usable:
        duration = result.duration_seconds if result.duration_seconds > 0 else 1.0
        weighted_energy += duration * math.pow(10.0, result.integrated_lufs / 10.0)
        total_duration += duration

    album_lufs = (
        10.0 * math.log10(weighted_energy / total_duration)
        if weighted_energy > 0 and total_duration > 0
        else None
    )

    # Album Peak = größter linearer Track-Peak (exakt).
    peaks = [
        result.replaygain_track_peak
        for result in usable
        if result.replaygain_track_peak is not None
    ]
    album_peak = max(peaks) if peaks else None

    return calculate_replaygain(album_lufs), album_peak


def analyze_album_loudness(
    filepaths: list[str],
) -> tuple[
    float | None,
    float | None,
]:
    existing_paths = [
        str(Path(filepath))
        for filepath in filepaths
        if Path(filepath).is_file()
    ]

    if not existing_paths:
        return None, None

    try:
        payload = _extract_loudness(existing_paths)
    except Exception:  # PyAV/Container-Fehler
        return None, None

    return (
        calculate_replaygain(payload.get("input_i")),
        db_to_linear(payload.get("input_tp")),
    )


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
