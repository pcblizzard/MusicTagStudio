from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from threading import Lock

from .models import CoverCandidate


CACHE_VERSION = 1
DEFAULT_MAX_AGE_DAYS = 30


class CoverSearchCache:
    """
    Dauerhafter Cache für Cover-Suchergebnisse.

    Gespeichert werden nur Metadaten wie URLs, IDs, Auflösung und Quelle.
    Bilddateien und Zugangsdaten werden nicht im Cache abgelegt.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ):
        self.path = (
            Path(path)
            if path is not None
            else default_cache_path()
        )
        self.max_age_seconds = (
            max(1, max_age_days) * 24 * 60 * 60
        )
        self._lock = Lock()

    def get(
        self,
        key: str,
    ) -> list[CoverCandidate] | None:
        with self._lock:
            payload = self._read()

            entry = payload.get(
                "entries",
                {},
            ).get(key)

            if not isinstance(entry, dict):
                return None

            timestamp = entry.get(
                "timestamp",
                0,
            )

            try:
                age = (
                    time.time()
                    - float(timestamp)
                )
            except (TypeError, ValueError):
                return None

            if age > self.max_age_seconds:
                self._remove_entry(
                    payload,
                    key,
                )
                self._write(payload)
                return None

            raw_candidates = entry.get(
                "candidates",
                [],
            )

            result: list[CoverCandidate] = []

            for raw_candidate in raw_candidates:
                if not isinstance(
                    raw_candidate,
                    dict,
                ):
                    continue

                try:
                    result.append(
                        CoverCandidate(
                            source=str(
                                raw_candidate.get(
                                    "source",
                                    "",
                                )
                            ),
                            source_label=str(
                                raw_candidate.get(
                                    "source_label",
                                    "",
                                )
                            ),
                            url=str(
                                raw_candidate.get(
                                    "url",
                                    "",
                                )
                            ),
                            width=int(
                                raw_candidate.get(
                                    "width",
                                    0,
                                )
                                or 0
                            ),
                            height=int(
                                raw_candidate.get(
                                    "height",
                                    0,
                                )
                                or 0
                            ),
                            mime=str(
                                raw_candidate.get(
                                    "mime",
                                    "",
                                )
                            ),
                            release_id=str(
                                raw_candidate.get(
                                    "release_id",
                                    "",
                                )
                            ),
                            score=int(
                                raw_candidate.get(
                                    "score",
                                    0,
                                )
                                or 0
                            ),
                            data=None,
                            preview_url=str(
                                raw_candidate.get(
                                    "preview_url",
                                    "",
                                )
                            ),
                            album=str(
                                raw_candidate.get(
                                    "album",
                                    "",
                                )
                            ),
                            artist=str(
                                raw_candidate.get(
                                    "artist",
                                    "",
                                )
                            ),
                            is_local=False,
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

            return result

    def put(
        self,
        key: str,
        candidates: list[CoverCandidate],
    ) -> None:
        online_candidates = [
            candidate
            for candidate in candidates
            if not candidate.is_local
        ]

        serializable = []

        for candidate in online_candidates:
            raw = asdict(candidate)
            raw.pop("data", None)
            raw["is_local"] = False
            serializable.append(raw)

        with self._lock:
            payload = self._read()
            entries = payload.setdefault(
                "entries",
                {},
            )
            entries[key] = {
                "timestamp": time.time(),
                "candidates": serializable,
            }
            self._write(payload)

    def clear(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()

    def _read(self) -> dict:
        if not self.path.is_file():
            return {
                "version": CACHE_VERSION,
                "entries": {},
            }

        try:
            data = json.loads(
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
            not isinstance(data, dict)
            or data.get("version")
            != CACHE_VERSION
        ):
            return {
                "version": CACHE_VERSION,
                "entries": {},
            }

        data.setdefault(
            "entries",
            {},
        )
        return data

    def _write(
        self,
        payload: dict,
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = self.path.with_suffix(
            ".tmp"
        )
        temporary.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    @staticmethod
    def _remove_entry(
        payload: dict,
        key: str,
    ) -> None:
        entries = payload.get(
            "entries",
            {},
        )

        if isinstance(entries, dict):
            entries.pop(key, None)


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
        / "cover_search.json"
    )
