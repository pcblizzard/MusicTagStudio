from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .metadata import MetadataCandidate


SourceStatus = Literal[
    "matched",
    "not_found",
    "error",
    "not_queried",
]


@dataclass(frozen=True)
class SourceProposal:
    source: str
    status: SourceStatus
    candidate: MetadataCandidate | None = None
    warnings: tuple[str, ...] = ()

    @property
    def has_candidate(self) -> bool:
        return self.candidate is not None
