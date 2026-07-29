"""Audio-Analyse über PyAV (gebündeltes FFmpeg) statt externer ffmpeg.exe.

PyAV liefert dieselbe FFmpeg-Version wie die frühere Standalone-Binärdatei,
aber als schlankes pip-Paket (~28 MB) – ohne 195-MB-Binärdateien, PATH-Suche
oder Subprozess. Genutzt werden:

- ``loudnorm`` (Messmodus) für integrierte Lautheit/True-Peak/LRA – die JSON-
  Ausgabe wird über ``av.logging.Capture`` eingefangen (identische Werte wie
  die CLI).
- ``showspectrumpic`` für das Spektrogramm-Bild.
- Container-/Stream-Eigenschaften für Codec/Abtastrate/Bit-Tiefe/Dauer.
"""

from __future__ import annotations

import json
from pathlib import Path

_LOUDNORM_ARGS = "I=-18:TP=-1:LRA=11:print_format=json"


def is_available() -> bool:
    try:
        import av  # noqa: F401
    except Exception:
        return False
    return True


def ffmpeg_version() -> str:
    try:
        import av

        info = getattr(av, "ffmpeg_version_info", "")
        return str(info or "")
    except Exception:
        return ""


def _drain(graph) -> list:
    import av

    frames = []
    while True:
        try:
            frames.append(graph.pull())
        except (av.error.BlockingIOError, av.error.EOFError):
            break
    return frames


def _parse_json_block(text: str) -> dict:
    start, end = text.rfind("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except ValueError:
        return {}


def measure_loudness_json(paths: list[str] | tuple[str, ...]) -> dict:
    """loudnorm-Messwerte für eine oder mehrere Dateien (Album zusammen).

    Gibt das rohe loudnorm-JSON zurück (Schlüssel input_i/input_tp/input_lra/
    input_thresh …). Mehrere Pfade werden – wie bei der Album-Analyse – als
    eine durchgehende Quelle gemessen.
    """
    import av
    import av.logging as avlog

    existing = [Path(p) for p in paths if Path(p).is_file()]
    if not existing:
        return {}

    avlog.set_level(avlog.INFO)
    with avlog.Capture() as logs:
        graph = None
        for index, path in enumerate(existing):
            container = av.open(str(path))
            stream = container.streams.audio[0]
            if graph is None:
                graph = av.filter.Graph()
                abuffer = graph.add_abuffer(template=stream)
                loud = graph.add("loudnorm", _LOUDNORM_ARGS)
                sink = graph.add("abuffersink")
                abuffer.link_to(loud)
                loud.link_to(sink)
                graph.configure()
            for frame in container.decode(stream):
                graph.push(frame)
                _drain(graph)
            container.close()
        if graph is not None:
            graph.push(None)
            _drain(graph)
            del graph  # Filter-Teardown -> loudnorm gibt seine JSON-Bilanz aus

    text = "\n".join(
        entry[-1] if isinstance(entry, tuple) else str(entry) for entry in logs
    )
    return _parse_json_block(text)


def render_spectrogram_png(
    filepath: str,
    output_path: str,
    *,
    width: int,
    height: int,
) -> None:
    """Erzeugt ein Spektrogramm-PNG via showspectrumpic (ein Videoframe)."""
    import av

    container = av.open(str(filepath))
    try:
        stream = container.streams.audio[0]
        graph = av.filter.Graph()
        abuffer = graph.add_abuffer(template=stream)
        spec = graph.add(
            "showspectrumpic",
            f"s={width}x{height}:legend=1:fscale=lin:color=intensity:scale=log",
        )
        sink = graph.add("buffersink")
        abuffer.link_to(spec)
        spec.link_to(sink)
        graph.configure()

        for frame in container.decode(stream):
            graph.push(frame)
        graph.push(None)

        for vframe in _drain(graph):
            vframe.to_image().save(output_path)
            return
        raise RuntimeError("showspectrumpic lieferte kein Bild.")
    finally:
        container.close()


def probe(filepath: str) -> dict:
    """Technische Eigenschaften (Codec/Rate/Bit-Tiefe/Kanäle/Dauer/Bitrate)."""
    import av

    with av.open(str(filepath)) as container:
        audio_streams = container.streams.audio
        if not audio_streams:
            return {}
        stream = audio_streams[0]
        codec_context = stream.codec_context
        fmt = getattr(codec_context, "format", None)
        bit_depth = int(getattr(fmt, "bits", 0) or 0) if fmt is not None else 0
        duration = 0.0
        if stream.duration is not None and stream.time_base is not None:
            duration = float(stream.duration * stream.time_base)
        elif container.duration is not None:
            duration = float(container.duration) / 1_000_000.0
        return {
            "codec": str(getattr(codec_context, "name", "") or ""),
            "container": str(getattr(container.format, "name", "") or ""),
            "sample_rate": int(getattr(codec_context, "sample_rate", 0) or 0),
            "bit_depth": bit_depth,
            "channels": int(getattr(codec_context, "channels", 0) or 0),
            "bitrate": int(
                getattr(codec_context, "bit_rate", 0)
                or getattr(container, "bit_rate", 0)
                or 0
            ),
            "duration_seconds": duration,
        }
