from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, order=True)
class LyricsLine:
    time_ms: int
    text: str = field(compare=False)


@dataclass(frozen=True)
class LyricsDocument:
    plain_text: str = ""
    synced_lines: tuple[LyricsLine, ...] = ()
    source: str = ""
    instrumental: bool = False
    metadata: dict[str, str] = field(default_factory=dict)
    provider_id: str = ""
    fetched_at: str = ""

    @property
    def is_synced(self) -> bool:
        return bool(self.synced_lines)

    @property
    def is_empty(self) -> bool:
        return (
            not self.instrumental
            and not self.plain_text.strip()
            and not self.synced_lines
        )

    def display_text(self) -> str:
        if self.instrumental and not self.plain_text.strip():
            return "Instrumental – kein Liedtext vorhanden."
        if self.plain_text.strip():
            return self.plain_text.strip()
        return "\n".join(line.text for line in self.synced_lines).strip()

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
