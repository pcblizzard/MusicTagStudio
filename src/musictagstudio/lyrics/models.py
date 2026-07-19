from __future__ import annotations

from dataclasses import dataclass, field


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

    @property
    def is_synced(self) -> bool:
        return bool(self.synced_lines)

    @property
    def is_empty(self) -> bool:
        return not self.plain_text.strip() and not self.synced_lines

    def display_text(self) -> str:
        if self.plain_text.strip():
            return self.plain_text.strip()
        return "\n".join(line.text for line in self.synced_lines).strip()
