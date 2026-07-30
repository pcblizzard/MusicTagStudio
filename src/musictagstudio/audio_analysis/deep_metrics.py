"""Tiefe Sample-Metriken (Peak/RMS/Dynamik/Clipping/Spektralschnitt) via PyAV.

Ergänzt die loudnorm-Messung (LUFS/True Peak) um Kennzahlen, die sich nur aus
den dekodierten Samples berechnen lassen – dieselben Werte wie in gängigen
Analyse-Apps:

- **Maximum**  – Spitzenpegel in dBFS (``20·log10(max|x|)``).
- **RMS**      – Effektivpegel in dBFS (``20·log10(√mean(x²))``).
- **Dynamik**  – Crest-Faktor ``Peak − RMS`` (in dB).
- **Clipping** – Anzahl Samples an/über Vollaussteuerung.
- **Spektralschnitt** – höchste Frequenz mit echter Energie (erkennt Lowpass /
  in FLAC umgepackte, verlustbehaftete Quellen).
- **Proben**   – Sample-Anzahl je Kanal.

Alles wird in **einem** Dekodier-Durchlauf ermittelt; die Samples werden nach
``fltp`` (planares Float in [-1, 1]) gewandelt, damit Peak/RMS formatunabhängig
stimmen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Ab diesem Betrag gilt ein Sample als vollausgesteuert (Clipping-Verdacht).
_CLIP_THRESHOLD = 0.9995
# FFT-Fenstergröße für die gemittelte Leistungsdichte (Welch-Verfahren).
_FFT_SIZE = 16384
# Ab wie viel dB unter dem Maximum die Energie als "nicht mehr vorhanden" gilt.
_CUTOFF_DROP_DB = 60.0


@dataclass(frozen=True)
class ChannelMetrics:
    peak_dbfs: float | None = None
    rms_dbfs: float | None = None
    dynamic_range_db: float | None = None
    clipped_samples: int = 0


@dataclass(frozen=True)
class DeepMetrics:
    decoded_format: str = ""
    sample_count: int = 0
    peak_dbfs: float | None = None
    rms_dbfs: float | None = None
    dynamic_range_db: float | None = None
    clipped_samples: int = 0
    spectral_cutoff_hz: float | None = None
    # Form der oberen Spektralkante (für die Echtheitsprüfung):
    # - spectral_shelf_db: mittlerer Pegel oberhalb der Kante, relativ zum
    #   Maximum (stark negativ = digitale Stille = künstliche Grenze).
    # - spectral_steepness_db: Abfall von der Kante zum darüberliegenden Regal
    #   (groß = steile „Brickwall" wie bei Transcodes).
    # Beide None, wenn die Kante zu nah an Nyquist liegt (Form nicht beurteilbar).
    spectral_shelf_db: float | None = None
    spectral_steepness_db: float | None = None
    channels: tuple[ChannelMetrics, ...] = ()


def _to_dbfs(amplitude: float) -> float | None:
    if amplitude <= 0.0:
        return None
    return 20.0 * math.log10(amplitude)


def analyze(filepath: str) -> DeepMetrics:
    """Berechnet die tiefen Sample-Metriken einer Datei in einem Durchlauf."""
    return _run(filepath, loudness=False)[0]


def analyze_full(filepath: str) -> tuple[DeepMetrics, dict]:
    """Sample-Metriken UND loudnorm-Messung in **einem** Dekodier-Durchlauf.

    Spart gegenüber getrennten Aufrufen einen kompletten Decode pro Datei. Die
    loudnorm-Werte bleiben identisch, da die nativen Frames unverändert in den
    Filtergraphen gehen; parallel werden die Samples nach ``fltp`` gewandelt und
    für die Sample-Statistik ausgewertet. Rückgabe ``(DeepMetrics, loud_raw)``
    mit dem rohen loudnorm-JSON (Schlüssel input_i/input_tp/…).
    """
    return _run(filepath, loudness=True)


def _run(filepath: str, *, loudness: bool) -> tuple[DeepMetrics, dict]:
    import av
    import av.logging as avlog
    import numpy as np

    from . import av_backend

    container = av.open(str(filepath))
    loud_raw: dict = {}
    try:
        streams = container.streams.audio
        if not streams:
            return DeepMetrics(), {}
        stream = streams[0]
        sample_rate = int(stream.codec_context.sample_rate or 0)
        decoded_format = str(getattr(stream.codec_context.format, "name", "") or "")
        resampler = av.AudioResampler(format="fltp")

        max_abs: list[float] = []
        sum_sq: list[float] = []
        counts: list[int] = []
        clipped: list[int] = []
        buffers: list[np.ndarray] = []
        psd: list[np.ndarray] = []
        blocks = 0
        window = np.hanning(_FFT_SIZE).astype(np.float32)

        def _ensure(channel_count: int) -> None:
            while len(max_abs) < channel_count:
                max_abs.append(0.0)
                sum_sq.append(0.0)
                counts.append(0)
                clipped.append(0)
                buffers.append(np.empty(0, dtype=np.float32))
                psd.append(np.zeros(_FFT_SIZE // 2 + 1, dtype=np.float64))

        def _consume(block_source: np.ndarray) -> None:
            nonlocal blocks
            channel_count = block_source.shape[0]
            _ensure(channel_count)
            for channel in range(channel_count):
                samples = block_source[channel]
                if samples.size == 0:
                    continue
                absolute = np.abs(samples)
                peak = float(absolute.max())
                if peak > max_abs[channel]:
                    max_abs[channel] = peak
                sum_sq[channel] += float(np.dot(samples, samples))
                counts[channel] += int(samples.size)
                clipped[channel] += int(np.count_nonzero(absolute >= _CLIP_THRESHOLD))
                buffers[channel] = np.concatenate([buffers[channel], samples])

            # Vollständige FFT-Blöcke aus den Puffern ziehen (gemittelte PSD).
            while all(buffers[c].size >= _FFT_SIZE for c in range(channel_count)):
                for channel in range(channel_count):
                    block = buffers[channel][:_FFT_SIZE] * window
                    spectrum = np.abs(np.fft.rfft(block)) ** 2
                    psd[channel] += spectrum
                    buffers[channel] = buffers[channel][_FFT_SIZE:]
                blocks += 1

        # Optional den loudnorm-Filter im selben Durchlauf mitlaufen lassen.
        graph = None
        capture = None
        logs = None
        if loudness:
            avlog.set_level(avlog.INFO)
            capture = avlog.Capture()
            logs = capture.__enter__()
            graph = av.filter.Graph()
            abuffer = graph.add_abuffer(template=stream)
            loud = graph.add("loudnorm", av_backend._LOUDNORM_ARGS)
            sink = graph.add("abuffersink")
            abuffer.link_to(loud)
            loud.link_to(sink)
            graph.configure()

        try:
            for frame in container.decode(stream):
                if graph is not None:
                    graph.push(frame)
                    av_backend._drain(graph)
                for resampled in resampler.resample(frame):
                    _consume(resampled.to_ndarray())
            for resampled in resampler.resample(None):
                _consume(resampled.to_ndarray())
            if graph is not None:
                graph.push(None)
                av_backend._drain(graph)
                del graph  # Teardown -> loudnorm gibt seine JSON-Bilanz aus
        finally:
            if capture is not None:
                capture.__exit__(None, None, None)

        if logs is not None:
            text = "\n".join(
                entry[-1] if isinstance(entry, tuple) else str(entry)
                for entry in logs
            )
            loud_raw = av_backend._parse_json_block(text)
    finally:
        container.close()

    if not counts:
        return DeepMetrics(decoded_format=decoded_format), loud_raw

    channel_metrics = tuple(
        _channel_metrics(max_abs[c], sum_sq[c], counts[c], clipped[c])
        for c in range(len(counts))
    )
    overall_peak = max(max_abs) if max_abs else 0.0
    total_samples = sum(counts)
    overall_rms_amp = math.sqrt(sum(sum_sq) / total_samples) if total_samples else 0.0
    overall_peak_db = _to_dbfs(overall_peak)
    overall_rms_db = _to_dbfs(overall_rms_amp)
    overall_dr = (
        overall_peak_db - overall_rms_db
        if overall_peak_db is not None and overall_rms_db is not None
        else None
    )

    cutoff_hz, shelf_db, steepness_db = _spectral_profile(psd, blocks, sample_rate)
    metrics = DeepMetrics(
        decoded_format=decoded_format,
        sample_count=max(counts),
        peak_dbfs=overall_peak_db,
        rms_dbfs=overall_rms_db,
        dynamic_range_db=overall_dr,
        clipped_samples=sum(clipped),
        spectral_cutoff_hz=cutoff_hz,
        spectral_shelf_db=shelf_db,
        spectral_steepness_db=steepness_db,
        channels=channel_metrics,
    )
    return metrics, loud_raw


def _channel_metrics(
    max_abs: float, sum_sq: float, count: int, clipped: int
) -> ChannelMetrics:
    peak_db = _to_dbfs(max_abs)
    rms_amp = math.sqrt(sum_sq / count) if count else 0.0
    rms_db = _to_dbfs(rms_amp)
    dynamic = (
        peak_db - rms_db if peak_db is not None and rms_db is not None else None
    )
    return ChannelMetrics(
        peak_dbfs=peak_db,
        rms_dbfs=rms_db,
        dynamic_range_db=dynamic,
        clipped_samples=clipped,
    )


# Breite des Fensters (Hz) oberhalb der Kante, in dem das „Regal" gemessen wird.
_SHELF_WINDOW_HZ = 2000.0
# Pegel (dB unter Maximum), an dem der eigentliche Inhalt endet (Content-Kante).
_EDGE_DROP_DB = 20.0


def _spectral_profile(
    psd, blocks: int, sample_rate: int
) -> tuple[float | None, float | None, float | None]:
    """Spektralschnitt plus Form der oberen Kante (Regal-Pegel, Steilheit).

    Rückgabe ``(cutoff_hz, shelf_db, steepness_db)``. ``shelf_db``/``steepness_db``
    sind ``None``, wenn die Kante zu nah an Nyquist liegt, um die Form seriös zu
    beurteilen (z. B. echtes Vollband-Material).
    """
    import numpy as np

    if blocks == 0 or sample_rate <= 0 or not psd:
        return None, None, None
    mean = np.mean(np.vstack(psd), axis=0) / blocks
    if not np.any(mean > 0):
        return None, None, None

    bins = len(mean)
    hz_per_bin = (sample_rate / 2.0) / (bins - 1)
    power_db = 10.0 * np.log10(np.maximum(mean, 1e-20))
    peak_db = float(power_db.max())

    # Anzeige-Spektralschnitt: höchste Frequenz noch nahe am Maximum (-60 dB).
    above_cut = np.nonzero(power_db >= peak_db - _CUTOFF_DROP_DB)[0]
    if above_cut.size == 0:
        return None, None, None
    cutoff_hz = float(int(above_cut.max()) * hz_per_bin)

    # Content-Kante bei -20 dB: darüber Steilheit und Regal-Pegel messen.
    above_edge = np.nonzero(power_db >= peak_db - _EDGE_DROP_DB)[0]
    if above_edge.size == 0:
        return cutoff_hz, None, None
    edge_bin = int(above_edge.max())
    shelf_start = edge_bin + max(1, int(_SHELF_WINDOW_HZ / hz_per_bin))
    if shelf_start >= bins - 1:
        # Kante praktisch an Nyquist -> Form nicht beurteilbar (Vollband).
        return cutoff_hz, None, None

    shelf_mean = float(power_db[shelf_start:].mean())
    shelf_db = shelf_mean - peak_db  # Regal-Pegel relativ zum Maximum
    steepness_db = float(power_db[edge_bin]) - shelf_mean  # Abfall Kante -> Regal
    return cutoff_hz, shelf_db, steepness_db
