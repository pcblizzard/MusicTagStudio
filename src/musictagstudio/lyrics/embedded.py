from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
from dataclasses import replace

from mutagen import File, MutagenError

from .models import LyricsDocument, LyricsLine


def read_embedded_lyrics(audio_path: str | Path) -> LyricsDocument | None:
    try:
        audio = File(str(audio_path), easy=False)
    except (MutagenError, OSError):
        return None
    if audio is None or audio.tags is None:
        return None
    variants = lyrics_variants_from_tags(audio.tags)
    return (
        replace(variants[0], source="Eingebettete Lyrics")
        if variants
        else None
    )


def read_embedded_lyrics_variants(
    audio_path: str | Path,
) -> tuple[LyricsDocument, ...]:
    try:
        audio = File(str(audio_path), easy=False)
    except (MutagenError, OSError):
        return ()
    if audio is None or audio.tags is None:
        return ()
    return lyrics_variants_from_tags(audio.tags)


def lyrics_from_tags(tags: Mapping[str, Any]) -> LyricsDocument | None:
    variants = lyrics_variants_from_tags(tags)
    return (
        replace(variants[0], source="Eingebettete Lyrics")
        if variants
        else None
    )


def lyrics_variants_from_tags(
    tags: Mapping[str, Any],
) -> tuple[LyricsDocument, ...]:
    variants: list[LyricsDocument] = []
    for key in tags.keys():
        value = tags[key]
        upper = str(key).upper()
        if upper.startswith("SYLT"):
            frame_lines: list[LyricsLine] = []
            for text, time_ms in getattr(value, "text", ()):
                frame_lines.append(LyricsLine(int(time_ms), str(text)))
            if frame_lines:
                variants.append(
                    LyricsDocument(
                        plain_text="\n".join(line.text for line in frame_lines),
                        synced_lines=tuple(sorted(frame_lines)),
                        source=f"Eingebettete Lyrics ({key})",
                    )
                )
        elif upper.startswith("USLT"):
            text = str(getattr(value, "text", value)).strip()
            if text:
                variants.append(
                    LyricsDocument(
                        plain_text=text,
                        source=f"Eingebettete Lyrics ({key})",
                    )
                )
        elif upper in {
            "LYRICS",
            "UNSYNCEDLYRICS",
            "©LYR",
            "\xa9LYR",
            "WM/LYRICS",
        }:
            for text in _text_values(value):
                if text.strip():
                    variants.append(
                        LyricsDocument(
                            plain_text=text.strip(),
                            source=f"Eingebettete Lyrics ({key})",
                        )
                    )
        elif upper in {"SYNCEDLYRICS", "SYNCED LYRICS"}:
            from .lrc import parse_lrc

            parsed = parse_lrc("\n".join(_text_values(value)))
            if not parsed.is_empty:
                variants.append(
                    LyricsDocument(
                        plain_text=parsed.plain_text,
                        synced_lines=parsed.synced_lines,
                        source=f"Eingebettete Lyrics ({key})",
                        metadata=parsed.metadata,
                    )
                )
    return tuple(variants)


def _text_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]
