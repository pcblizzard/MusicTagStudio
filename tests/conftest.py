from __future__ import annotations

import pytest

from musictagstudio.providers import http_cache


@pytest.fixture(autouse=True)
def _isolate_http_cache(monkeypatch, tmp_path):
    """
    Hält den Provider-Antwort-Cache aus den Tests heraus.

    Ohne diese Isolation würde jeder Testlauf in das echte Projekt-
    Cache-Verzeichnis schreiben und spätere Tests (etwa Retry-Zählungen)
    mit zwischengespeicherten Antworten verfälschen.
    """
    monkeypatch.setattr(
        http_cache,
        "project_root",
        lambda: tmp_path,
    )
