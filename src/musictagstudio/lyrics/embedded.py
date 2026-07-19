from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from mutagen import File

from .models import LyricsDocument, LyricsLine


def read_embedded_lyrics(audio_path: str | Path) -> LyricsDocument | None:
    audio = File(str(audio_path), easy=False)
    if audio is None or audio.tags is None:
        return None
    return lyrics_from_tags(audio.tags)


def lyrics_from_tags(tags: Mapping[str, Any]) -> LyricsDocument | None:
    synced: list[LyricsLine] = []
    plain_candidates: list[str] = []
    for key in tags.keys():
        value = tags[key]
        upper = str(key).upper()
        if upper.startswith("SYLT"):
            for text, time_ms in getattr(value, "text", ()):
                synced.append(LyricsLine(int(time_ms), str(text)))
        elif upper.startswith("USLT"):
            plain_candidates.append(str(getattr(value, "text", value)))
        elif upper in {
            "LYRICS",
            "UNSYNCEDLYRICS",
            "©LYR",
            "\xa9LYR",
        }:
            plain_candidates.extend(_text_values(value))
        elif upper in {"SYNCEDLYRICS", "SYNCED LYRICS"}:
            from .lrc import parse_lrc

            parsed = parse_lrc("\n".join(_text_values(value)))
            synced.extend(parsed.synced_lines)
            if parsed.plain_text:
                plain_candidates.append(parsed.plain_text)
    plain = next((text.strip() for text in plain_candidates if text.strip()), "")
    if not plain and synced:
        plain = "\n".join(line.text for line in sorted(synced)).strip()
    if not plain and not synced:
        return None
    return LyricsDocument(
        plain_text=plain,
        synced_lines=tuple(sorted(synced)),
        source="Eingebettete Lyrics",
    )


def _text_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]
