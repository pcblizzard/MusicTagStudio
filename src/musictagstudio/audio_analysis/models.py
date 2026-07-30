from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class FFmpegInstallation:
    ffmpeg_path: str
    ffprobe_path: str
    version: str = ""

    @property
    def available(self) -> bool:
        return bool(
            self.ffmpeg_path
            and self.ffprobe_path
        )


@dataclass(frozen=True)
class AudioAnalysisResult:
    path: str
    codec: str = ""
    container: str = ""
    sample_rate: int = 0
    bit_depth: int = 0
    channels: int = 0
    channel_layout: str = ""
    bitrate: int = 0
    duration_seconds: float = 0.0
    file_size: int = 0

    integrated_lufs: float | None = None
    loudness_range_lu: float | None = None
    true_peak_db: float | None = None
    threshold_lufs: float | None = None

    # Tiefe Sample-Metriken (deep_metrics). Pro-Kanal-Werte als flache Tupel,
    # damit der JSON-Cache sie ohne verschachtelte Dataclasses speichern kann.
    decoded_format: str = ""
    sample_count: int = 0
    peak_dbfs: float | None = None
    rms_dbfs: float | None = None
    dynamic_range_db: float | None = None
    clipped_samples: int = 0
    spectral_cutoff_hz: float | None = None
    spectral_shelf_db: float | None = None
    spectral_steepness_db: float | None = None
    channel_peaks_dbfs: tuple[float | None, ...] = ()
    channel_rms_dbfs: tuple[float | None, ...] = ()
    channel_dynamic_range_db: tuple[float | None, ...] = ()
    channel_clipped_samples: tuple[int, ...] = ()

    replaygain_track_gain_db: float | None = None
    replaygain_track_peak: float | None = None
    replaygain_album_gain_db: float | None = None
    replaygain_album_peak: float | None = None

    peak_status: str = "unknown"
    from_cache: bool = False
    error: str = ""

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def sample_rate_text(self) -> str:
        if not self.sample_rate:
            return ""

        return f"{self.sample_rate / 1000:.1f} kHz"

    @property
    def bitrate_text(self) -> str:
        if not self.bitrate:
            return ""

        return f"{self.bitrate / 1000:.0f} kbit/s"

    @property
    def duration_text(self) -> str:
        if self.duration_seconds <= 0:
            return ""

        total_seconds = round(
            self.duration_seconds
        )
        minutes, seconds = divmod(
            total_seconds,
            60,
        )
        hours, minutes = divmod(
            minutes,
            60,
        )

        if hours:
            return (
                f"{hours}:{minutes:02d}:"
                f"{seconds:02d}"
            )

        return f"{minutes}:{seconds:02d}"

    @property
    def nyquist_hz(self) -> float:
        return self.sample_rate / 2.0 if self.sample_rate else 0.0

    @property
    def nyquist_text(self) -> str:
        return f"{self.nyquist_hz / 1000:.1f} kHz" if self.sample_rate else ""

    @property
    def file_size_text(self) -> str:
        if self.file_size <= 0:
            return ""
        megabytes = self.file_size / (1024 * 1024)
        return f"{megabytes:.1f} MB"

    @property
    def sample_count_text(self) -> str:
        if self.sample_count <= 0:
            return ""
        if self.sample_count >= 1_000_000:
            return f"{self.sample_count / 1_000_000:.1f}M"
        if self.sample_count >= 1_000:
            return f"{self.sample_count / 1_000:.0f}K"
        return str(self.sample_count)

    @property
    def clipping_text(self) -> str:
        if self.clipped_samples <= 0:
            return "Kein Clipping"
        return f"{self.clipped_samples} Stellen"

    @property
    def spectral_cutoff_text(self) -> str:
        if not self.spectral_cutoff_hz:
            return ""
        return f"{self.spectral_cutoff_hz / 1000:.1f} kHz"

    @property
    def channel_count(self) -> int:
        return len(self.channel_peaks_dbfs)

    @property
    def technical_signature(
        self,
    ) -> tuple[object, ...]:
        return (
            self.codec.casefold(),
            self.sample_rate,
            self.bit_depth,
            self.channels,
        )

    @property
    def has_peak_warning(self) -> bool:
        return self.peak_status in {
            "elevated",
            "over_zero",
            "critical",
        }

    def with_album_replaygain(
        self,
        gain_db: float | None,
        peak: float | None,
    ) -> "AudioAnalysisResult":
        return replace(
            self,
            replaygain_album_gain_db=gain_db,
            replaygain_album_peak=peak,
        )

    def as_cached(
        self,
    ) -> "AudioAnalysisResult":
        return replace(
            self,
            from_cache=True,
        )


@dataclass(frozen=True)
class AlbumAnalysisSummary:
    album_key: tuple[str, str]
    display_name: str
    track_count: int
    dominant_signature: tuple[object, ...] | None
    average_bitrate: float | None
    average_lufs: float | None
    album_gain_db: float | None
    album_peak: float | None
    technical_outliers: tuple[str, ...]
    elevated_peak_files: tuple[str, ...]
    over_zero_peak_files: tuple[str, ...]
    critical_peak_files: tuple[str, ...]
    missing_analysis_files: tuple[str, ...]
    health_score: int

    @property
    def has_warnings(self) -> bool:
        return bool(
            self.technical_outliers
            or self.elevated_peak_files
            or self.over_zero_peak_files
            or self.critical_peak_files
            or self.missing_analysis_files
        )

    @property
    def peak_warning_count(self) -> int:
        return (
            len(self.elevated_peak_files)
            + len(self.over_zero_peak_files)
            + len(self.critical_peak_files)
        )
