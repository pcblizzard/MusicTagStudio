"""Echtheits-Einschätzung: echtes (Hi-Res-)Lossless oder hochgerechnet?

Vergleicht den gemessenen **Spektralschnitt** (höchste Frequenz mit echter
Energie, aus :mod:`deep_metrics`) mit der deklarierten Sample-Rate und dem
Codec. Typische Fingerabdrücke:

- **Als Hi-Res verkauft (≥ 88,2 kHz), aber kein Inhalt über ~24 kHz** →
  vermutlich aus einer 44,1/48-kHz-Quelle hochgerechnet.
- **Lossless bei 44,1/48 kHz mit harter Grenze bei ~16 kHz** → riecht nach
  einer MP3-Quelle mit niedriger Bitrate.

Bewusst **vorsichtig** formuliert: Manche echten Aufnahmen enthalten von Natur
aus wenig Hochton. Das Ergebnis ist ein begründeter Hinweis, kein Beweis.
"""

from __future__ import annotations

from dataclasses import dataclass

# Codecs, die verlustfrei speichern (av-/ffmpeg-Namen).
_LOSSLESS_CODECS = frozenset(
    {"flac", "alac", "wavpack", "tak", "ape", "truehd", "mlp", "tta", "als"}
)

# Ab dieser Sample-Rate gilt eine Datei als „Hi-Res" deklariert.
_HIRES_RATE = 88_200
# Echter Hi-Res-Inhalt zeigt Energie deutlich über der CD-Grenze.
_HIRES_MIN_CUTOFF = 24_000
# Harte Grenze in diesem Bereich deutet auf MP3 mit niedriger Bitrate.
_MP3_CUTOFF = 16_500
# Grenzbereich, in dem eine verlustbehaftete Quelle plausibel ist.
_LOSSY_CUTOFF = 19_000

# Formkriterien der oberen Kante (aus deep_metrics):
# - Regal oberhalb der Kante liegt so tief unter dem Maximum -> „digitale Stille".
_SILENT_SHELF_DB = -80.0
# - Abfall von der Kante zum Regal so groß -> steile „Brickwall".
_STEEP_EDGE_DB = 45.0


@dataclass(frozen=True)
class Authenticity:
    level: str  # genuine | suspect | fake | lossy | unknown
    message_key: str
    cutoff_hz: float | None = None
    confidence: str = "medium"  # high | medium | low


def is_lossless_codec(codec: str) -> bool:
    name = (codec or "").strip().lower()
    return name in _LOSSLESS_CODECS or name.startswith("pcm_")


def _brickwall_confidence(
    shelf_db: float | None, steepness_db: float | None
) -> str:
    """Wie sicher deutet die Kantenform auf eine künstliche Grenze hin?

    ``high``  = steile Kante UND digitale Stille darüber (klarer Transcode).
    ``medium``= eines von beiden.
    ``low``   = Form spricht dagegen oder ist nicht beurteilbar (sanfter Abfall
    mit Restenergie -> eher echter, natürlicher Höhenabfall).
    """
    if shelf_db is None or steepness_db is None:
        return "low"  # Form nicht beurteilbar -> nicht überbewerten
    silent = shelf_db <= _SILENT_SHELF_DB
    steep = steepness_db >= _STEEP_EDGE_DB
    if silent and steep:
        return "high"
    if silent or steep:
        return "medium"
    return "low"


def assess(
    *,
    codec: str,
    sample_rate: int,
    spectral_cutoff_hz: float | None,
    shelf_db: float | None = None,
    steepness_db: float | None = None,
) -> Authenticity:
    """Urteil aus Codec, Sample-Rate, Spektralschnitt und Kantenform.

    Die Kantenform (``shelf_db``/``steepness_db``) macht die Einschätzung robust:
    Ein rotes Urteil fällt nur, wenn eine tiefe Grenze mit einer künstlichen
    Kante (steil + digitale Stille darüber) zusammentrifft. Ein natürlicher,
    sanfter Höhenabfall bleibt „grenzwertig" statt fälschlich „Fake".
    """
    if not is_lossless_codec(codec):
        # Ehrlich verlustbehaftet – kein „Fake", nur eben kein Lossless/Hi-Res.
        return Authenticity("lossy", "auth_lossy", spectral_cutoff_hz, "high")

    if spectral_cutoff_hz is None or sample_rate <= 0:
        return Authenticity("unknown", "auth_unknown", spectral_cutoff_hz, "low")

    confidence = _brickwall_confidence(shelf_db, steepness_db)

    # Als Hi-Res deklariert -> es sollte Inhalt oberhalb der CD-Grenze geben.
    if sample_rate >= _HIRES_RATE:
        brickwall = confidence in ("high", "medium")
        # Verdächtig, wenn (a) der Inhalt schon unter ~24 kHz endet ODER (b) eine
        # künstliche Kante existiert (steil + Stille darüber) – Letzteres greift
        # auch, wenn der -60-dB-Schnitt durch Resampler-Ausläufer knapp über der
        # Schwelle liegt (typisch bei 44,1 kHz -> 96 kHz hochgerechnet).
        if spectral_cutoff_hz < _HIRES_MIN_CUTOFF or brickwall:
            effective = confidence if brickwall else "medium"
            level = "fake" if effective in ("high", "medium") else "suspect"
            return Authenticity(
                level, "auth_upsampled", spectral_cutoff_hz, effective
            )
        return Authenticity(
            "genuine", "auth_genuine_hires", spectral_cutoff_hz, "high"
        )

    # CD-Auflösung (44,1/48 kHz): tiefe Grenze nur mit passender Kantenform rot.
    if spectral_cutoff_hz <= _MP3_CUTOFF:
        if confidence in ("high", "medium"):
            return Authenticity(
                "fake", "auth_suspect_mp3", spectral_cutoff_hz, confidence
            )
        return Authenticity(
            "suspect", "auth_suspect_lossy", spectral_cutoff_hz, "low"
        )
    if spectral_cutoff_hz <= _LOSSY_CUTOFF:
        # Grenzbereich: nur bei klarer Brickwall überhaupt „Fake".
        if confidence == "high":
            return Authenticity(
                "fake", "auth_suspect_mp3", spectral_cutoff_hz, "high"
            )
        level = "suspect" if confidence == "medium" else "genuine"
        key = (
            "auth_suspect_lossy" if level == "suspect" else "auth_genuine_lossless"
        )
        return Authenticity(level, key, spectral_cutoff_hz, confidence)
    return Authenticity(
        "genuine", "auth_genuine_lossless", spectral_cutoff_hz, "high"
    )
