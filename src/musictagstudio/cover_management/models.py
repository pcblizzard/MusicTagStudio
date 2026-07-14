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

    @property
    def dimensions(self) -> str:
        if self.width and self.height:
            return f"{self.width} × {self.height}"

        return "wird beim Download ermittelt"

    def with_data(
        self,
        data: bytes,
        *,
        width: int,
        height: int,
        mime: str,
        score: int | None = None,
    ) -> "CoverCandidate":
        return replace(
            self,
            data=data,
            width=width,
            height=height,
            mime=mime,
            score=self.score if score is None else score,
        )
