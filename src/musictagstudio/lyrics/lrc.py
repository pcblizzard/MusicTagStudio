from __future__ import annotations

import re

from .models import LyricsDocument, LyricsLine


_TIMESTAMP = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
_METADATA = re.compile(r"^\[([A-Za-z][A-Za-z0-9_-]*):(.*)\]$")


def parse_lrc(text: str, *, source: str = "LRC") -> LyricsDocument:
    metadata: dict[str, str] = {}
    synced: list[LyricsLine] = []
    plain: list[str] = []
    synced_plain: list[str] = []

    for raw_line in str(text or "").replace("\r\n", "\n").split("\n"):
        timestamps = list(_TIMESTAMP.finditer(raw_line))
        if timestamps:
            lyric = _TIMESTAMP.sub("", raw_line).strip()
            synced_plain.append(lyric)
            for match in timestamps:
                fraction = (match.group(3) or "0")
                fraction_ms = int(fraction.ljust(3, "0")[:3])
                time_ms = (
                    int(match.group(1)) * 60_000
                    + int(match.group(2)) * 1_000
                    + fraction_ms
                )
                synced.append(LyricsLine(time_ms, lyric))
            continue
        tag = _METADATA.match(raw_line.strip())
        if tag:
            metadata[tag.group(1).lower()] = tag.group(2).strip()
        else:
            plain.append(raw_line.rstrip())

    offset = _parse_offset(metadata.pop("offset", ""))
    if offset:
        synced = [
            LyricsLine(max(0, line.time_ms + offset), line.text)
            for line in synced
        ]
    synced.sort()
    plain_text = "\n".join(plain).strip("\n")
    if not plain_text and synced:
        plain_text = "\n".join(synced_plain).strip("\n")
    return LyricsDocument(
        plain_text=plain_text,
        synced_lines=tuple(synced),
        source=source,
        metadata=metadata,
        instrumental=metadata.get("instrumental", "").casefold() in {
            "1", "true", "yes", "ja",
        },
    )


def render_lrc(document: LyricsDocument) -> str:
    metadata = dict(document.metadata)
    if document.instrumental and not document.plain_text and not document.synced_lines:
        metadata["instrumental"] = "true"
    lines = [
        f"[{key}:{value}]"
        for key, value in metadata.items()
        if key != "offset" and value
    ]
    if lines and (document.synced_lines or document.plain_text):
        lines.append("")
    if document.synced_lines:
        for line in sorted(document.synced_lines):
            minutes, remainder = divmod(max(0, line.time_ms), 60_000)
            seconds, milliseconds = divmod(remainder, 1_000)
            lines.append(
                f"[{minutes:02d}:{seconds:02d}.{milliseconds // 10:02d}]"
                f"{line.text}"
            )
    elif document.plain_text:
        lines.extend(document.plain_text.splitlines())
    return "\n".join(lines).rstrip() + "\n"


def _parse_offset(value: str) -> int:
    try:
        return int(value.strip())
    except (AttributeError, TypeError, ValueError):
        return 0
