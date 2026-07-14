from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from threading import Lock

from .models import AudioAnalysisResult


CACHE_VERSION = 1
ANALYSIS_VERSION = "0.6.4"


class AudioAnalysisCache:
    """
    Dauerhafter Cache für Audioanalysen.

    Eine Datei gilt nur dann als unverändert, wenn absoluter Pfad,
    Dateigröße und Änderungszeitpunkt übereinstimmen.
    """

    def __init__(
        self,
        path: str | Path | None = None,
    ):
        self.path = (
            Path(path)
            if path is not None
            else default_cache_path()
        )
        self._lock = Lock()

    def get(
        self,
        filepath: str | Path,
    ) -> AudioAnalysisResult | None:
        path = Path(filepath)

        if not path.is_file():
            return None

        key = str(path.resolve()).casefold()
        fingerprint = file_fingerprint(path)

        with self._lock:
            payload = self._read()
            entry = payload.get(
                "entries",
                {},
            ).get(key)

        if not isinstance(entry, dict):
            return None

        if entry.get("fingerprint") != fingerprint:
            return None

        if entry.get("analysis_version") != ANALYSIS_VERSION:
            return None

        raw_result = entry.get("result")

        if not isinstance(raw_result, dict):
            return None

        try:
            raw_result["from_cache"] = True
            return AudioAnalysisResult(
                **raw_result
            )
        except TypeError:
            return None

    def put(
        self,
        result: AudioAnalysisResult,
    ) -> None:
        path = Path(result.path)

        if (
            not path.is_file()
            or result.error
        ):
            return

        key = str(path.resolve()).casefold()
        stored_result = asdict(result)
        stored_result["from_cache"] = False

        with self._lock:
            payload = self._read()
            entries = payload.setdefault(
                "entries",
                {},
            )
            entries[key] = {
                "fingerprint": file_fingerprint(path),
                "analysis_version": ANALYSIS_VERSION,
                "timestamp": time.time(),
                "result": stored_result,
            }
            self._write(payload)

    def clear(self) -> None:
        with self._lock:
            self.path.unlink(
                missing_ok=True
            )

    def _read(self) -> dict:
        if not self.path.is_file():
            return {
                "version": CACHE_VERSION,
                "entries": {},
            }

        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return {
                "version": CACHE_VERSION,
                "entries": {},
            }

        if (
            not isinstance(payload, dict)
            or payload.get("version")
            != CACHE_VERSION
        ):
            return {
                "version": CACHE_VERSION,
                "entries": {},
            }

        payload.setdefault(
            "entries",
            {},
        )
        return payload

    def _write(
        self,
        payload: dict,
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary_path = self.path.with_suffix(
            ".tmp"
        )
        temporary_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(
            self.path
        )


def file_fingerprint(
    path: Path,
) -> dict[str, int]:
    stat = path.stat()

    return {
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def default_cache_path() -> Path:
    local_app_data = os.environ.get(
        "LOCALAPPDATA"
    )

    if local_app_data:
        base = Path(local_app_data)
    else:
        base = (
            Path.home()
            / ".cache"
        )

    return (
        base
        / "MusicTagStudio"
        / "audio_analysis.json"
    )
