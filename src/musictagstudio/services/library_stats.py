"""Bibliotheks-Qualitätsstatistik: Verteilung über Format/Auflösung/Kanäle.

Nutzt die schnelle, offline-fähige :func:`probe_quality` (mutagen) und fasst
die Sammlung zusammen: Anteil verlustfrei/verlustbehaftet, Codecs, Bit-Tiefen,
Abtastraten. So sieht man auf einen Blick, wie „hochwertig" die Sammlung ist.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..audio_analysis.quality import probe_quality


@dataclass(frozen=True)
class LibraryStats:
    total: int = 0
    readable: int = 0
    lossless: int = 0
    lossy: int = 0
    by_codec: dict[str, int] = field(default_factory=dict)
    by_bit_depth: dict[int, int] = field(default_factory=dict)
    by_sample_rate: dict[int, int] = field(default_factory=dict)

    @property
    def lossless_percent(self) -> float:
        return 100.0 * self.lossless / self.readable if self.readable else 0.0


def compute_stats(paths: list[str]) -> LibraryStats:
    """Liest die Qualität aller Pfade und fasst die Verteilung zusammen."""
    readable = 0
    lossless = 0
    lossy = 0
    codecs: Counter[str] = Counter()
    bit_depths: Counter[int] = Counter()
    sample_rates: Counter[int] = Counter()

    for path in paths:
        quality = probe_quality(path)
        if not quality.ok:
            continue
        readable += 1
        if quality.lossless:
            lossless += 1
        else:
            lossy += 1
        if quality.codec:
            codecs[quality.codec] += 1
        if quality.lossless and quality.bit_depth:
            bit_depths[quality.bit_depth] += 1
        if quality.sample_rate:
            sample_rates[quality.sample_rate] += 1

    return LibraryStats(
        total=len(paths),
        readable=readable,
        lossless=lossless,
        lossy=lossy,
        by_codec=dict(codecs.most_common()),
        by_bit_depth=dict(sorted(bit_depths.items())),
        by_sample_rate=dict(sorted(sample_rates.items())),
    )
