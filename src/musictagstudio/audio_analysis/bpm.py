"""BPM-Erkennung (Tempo) über PyAV + NumPy – ohne externe Tools.

Verfahren (klassisch, robust genug für Tempo-Filter):
1. Audio nach Mono dekodieren und auf eine niedrige Rate bringen (schnell).
2. **Onset-Hüllkurve** über spektralen Fluss (positive Energiezunahme je Frame).
3. **Autokorrelation** der Hüllkurve; das stärkste periodische Muster im
   Bereich ~60–200 BPM ergibt das Tempo.

Absichtlich schlank: analysiert standardmäßig nur die erste Minute. Liefert
eine gerundete BPM-Zahl oder ``None``, wenn nichts Verlässliches gefunden wird.
"""

from __future__ import annotations

_TARGET_RATE = 11025
_FRAME = 512
_HOP = 128
_MIN_BPM = 60.0
_MAX_BPM = 200.0


def detect_bpm(filepath: str, *, max_seconds: float = 60.0) -> float | None:
    """Schätzt das Tempo (BPM) einer Datei; ``None`` bei Fehlschlag."""
    import av
    import numpy as np

    try:
        container = av.open(str(filepath))
    except Exception:
        return None
    try:
        streams = container.streams.audio
        if not streams:
            return None
        stream = streams[0]
        resampler = av.AudioResampler(format="flt", layout="mono", rate=_TARGET_RATE)
        chunks: list = []
        collected = 0
        limit = int(max_seconds * _TARGET_RATE)
        for frame in container.decode(stream):
            for resampled in resampler.resample(frame):
                data = resampled.to_ndarray().reshape(-1)
                chunks.append(data)
                collected += data.size
            if collected >= limit:
                break
    except Exception:
        return None
    finally:
        container.close()

    if not chunks:
        return None
    signal = np.concatenate(chunks)[:limit].astype(np.float64)
    return _tempo_from_signal(signal, _TARGET_RATE)


def _tempo_from_signal(signal, sample_rate: int) -> float | None:
    import numpy as np

    if signal.size < _FRAME * 4:
        return None

    # Spektraler Fluss als Onset-Hüllkurve.
    window = np.hanning(_FRAME)
    prev_mag = None
    envelope: list[float] = []
    for start in range(0, signal.size - _FRAME, _HOP):
        frame = signal[start : start + _FRAME] * window
        mag = np.abs(np.fft.rfft(frame))
        if prev_mag is not None:
            flux = np.sum(np.maximum(mag - prev_mag, 0.0))
            envelope.append(float(flux))
        prev_mag = mag

    env = np.asarray(envelope, dtype=np.float64)
    if env.size < 8 or not np.any(env):
        return None
    env -= env.mean()

    env_rate = sample_rate / _HOP  # Hüllkurven-Abtastrate (Frames/s)
    min_lag = int(round(60.0 * env_rate / _MAX_BPM))
    max_lag = int(round(60.0 * env_rate / _MIN_BPM))
    max_lag = min(max_lag, env.size - 1)
    if min_lag < 1 or max_lag <= min_lag:
        return None

    # Autokorrelation nur im interessanten Lag-Bereich.
    autocorr = np.correlate(env, env, mode="full")
    autocorr = autocorr[autocorr.size // 2 :]  # nicht-negative Lags
    segment = autocorr[min_lag : max_lag + 1]
    if segment.size == 0 or not np.any(segment > 0):
        return None
    best_lag = min_lag + int(np.argmax(segment))
    if best_lag <= 0:
        return None

    # Parabolische Interpolation um den Peak -> Sub-Sample-genaues Lag, das die
    # grobe Ganzzahl-Auflösung der Autokorrelation ausgleicht.
    refined = float(best_lag)
    if 0 < best_lag < autocorr.size - 1:
        left = autocorr[best_lag - 1]
        center = autocorr[best_lag]
        right = autocorr[best_lag + 1]
        denom = left - 2.0 * center + right
        if denom != 0:
            offset = 0.5 * (left - right) / denom
            if -1.0 < offset < 1.0:
                refined = best_lag + offset

    return round(60.0 * env_rate / refined, 1)
