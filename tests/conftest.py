from __future__ import annotations

import pytest

from musictagstudio import i18n
from musictagstudio.providers import http_cache


@pytest.fixture(autouse=True)
def _pin_automatic_language(monkeypatch):
    """
    Legt die Sprache für ``language="automatic"`` deterministisch auf Deutsch.

    Viele UI-Tests prüfen den deutschen Anzeigetext. Ohne diese Fixierung
    haengt ``automatic`` am System-Locale der Maschine: lokal (DE) gruen, auf
    dem CI-Runner (EN) rot. Das Pinnen macht die Testsuite locale-unabhaengig.
    Tests mit explizitem ``language=`` (z. B. "en") sind davon unberuehrt.
    """
    monkeypatch.setattr(i18n, "system_language", lambda: "de")


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
