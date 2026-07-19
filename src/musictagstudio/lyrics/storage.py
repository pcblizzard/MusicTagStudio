from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .lrc import parse_lrc, render_lrc
from .models import LyricsDocument


def sidecar_path(audio_path: str | Path) -> Path:
    return Path(audio_path).with_suffix(".lrc")


def load_sidecar(audio_path: str | Path) -> LyricsDocument | None:
    path = sidecar_path(audio_path)
    if not path.is_file():
        return None
    return parse_lrc(path.read_text(encoding="utf-8-sig"), source="LRC-Datei")


def save_sidecar(
    audio_path: str | Path,
    document: LyricsDocument,
) -> Path:
    if document.is_empty:
        raise ValueError("Leere Lyrics werden nicht gespeichert.")
    destination = sidecar_path(audio_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(render_lrc(document))
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink(missing_ok=True)
    return destination
