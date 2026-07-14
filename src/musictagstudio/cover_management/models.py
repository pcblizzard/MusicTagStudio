from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class CoverCandidate:
    source: str
    source_label: str
    url: str
    width: int = 0
    height: int = 0
    mime: str = ""
    release_id: str = ""
    score: int = 0
    data: bytes | None = None
    preview_url: str = ""
    album: str = ""
    artist: str = ""
    is_local: bool = False
    file_size: int = 0
    md5: str = ""

    @property
    def dimensions(self) -> str:
        if self.width and self.height:
            return f"{self.width} × {self.height}"

        return "wird beim Download ermittelt"

    @property
    def file_size_text(self) -> str:
        if self.file_size <= 0:
            return "unbekannt"

        size = float(self.file_size)
        units = ("B", "KB", "MB", "GB")
        unit = units[0]

        for candidate_unit in units:
            unit = candidate_unit

            if size < 1024 or candidate_unit == units[-1]:
                break

            size /= 1024

        return f"{size:.1f} {unit}"

    @property
    def aspect_ratio_text(self) -> str:
        if not self.width or not self.height:
            return "unbekannt"

        if self.width == self.height:
            return "quadratisch"

        return f"{self.width / self.height:.3f}:1"

    @property
    def short_hash(self) -> str:
        if not self.md5:
            return ""

        return self.md5[:12]

    @property
    def quality_summary(self) -> str:
        mime = self.mime or "Format unbekannt"

        return (
            f"{self.dimensions} · {mime} · "
            f"{self.file_size_text} · "
            f"{self.aspect_ratio_text}"
        )

    def with_data(
        self,
        data: bytes,
        *,
        width: int,
        height: int,
        mime: str,
        score: int | None = None,
        md5: str = "",
    ) -> "CoverCandidate":
        return replace(
            self,
            data=data,
            width=width,
            height=height,
            mime=mime,
            score=self.score if score is None else score,
            file_size=len(data),
            md5=md5,
        )
