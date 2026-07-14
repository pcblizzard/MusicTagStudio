from dataclasses import dataclass

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

    @property
    def dimensions(self) -> str:
        return f"{self.width} × {self.height}" if self.width and self.height else "unbekannt"
