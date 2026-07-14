from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Severity = Literal[
    "info",
    "warning",
    "error",
]


@dataclass(frozen=True)
class LibraryIssue:
    category: str
    severity: Severity
    message: str
    album_artist: str = ""
    album: str = ""
    title: str = ""
    path: str = ""
    details: str = ""

    @property
    def album_display(self) -> str:
        if self.album_artist and self.album:
            return (
                f"{self.album_artist} – "
                f"{self.album}"
            )

        return self.album or self.album_artist


@dataclass(frozen=True)
class LibraryAuditSummary:
    checked_files: int
    checked_albums: int
    issues: tuple[LibraryIssue, ...]

    @property
    def warning_count(self) -> int:
        return sum(
            issue.severity == "warning"
            for issue in self.issues
        )

    @property
    def error_count(self) -> int:
        return sum(
            issue.severity == "error"
            for issue in self.issues
        )

    @property
    def info_count(self) -> int:
        return sum(
            issue.severity == "info"
            for issue in self.issues
        )

    @property
    def health_score(self) -> int:
        score = 100
        score -= min(
            45,
            self.error_count * 6,
        )
        score -= min(
            35,
            self.warning_count * 2,
        )
        score -= min(
            10,
            self.info_count,
        )

        return max(
            0,
            score,
        )
