from __future__ import annotations

import json

import pytest

from musictagstudio import i18n, licensing_keygen, usage_limits
from musictagstudio.providers import http_cache


@pytest.fixture(autouse=True)
def _isolate_license(request, monkeypatch, tmp_path):
    """
    Hält die Online-Lizenzprüfung (Keygen) und das Gratis-Kontingent aus den
    Tests heraus.

    Sonst würde ein in der echten config.toml hinterlegter Lizenzschlüssel bei
    jedem Fenster-/Dialogaufbau eine echte Netzwerkanfrage auslösen (Timeouts,
    Flakiness). is_configured -> False verhindert jede Online-Prüfung; Cache-
    und Nutzungszähler zeigen auf ein leeres Temp-Verzeichnis.

    Die reinen Keygen-Logiktests (mit eingespeistem Transport) brauchen den
    konfigurierten Zustand und schalten die Isolation per Marker ``real_license``
    ab.
    """
    if request.node.get_closest_marker("real_license") is not None:
        return
    monkeypatch.setattr(licensing_keygen, "is_configured", lambda: False)
    monkeypatch.setattr(
        licensing_keygen,
        "default_cache_path",
        lambda: tmp_path / "license_cache.json",
    )
    usage_file = tmp_path / "usage.json"
    monkeypatch.setattr(
        usage_limits,
        "default_usage_path",
        lambda: usage_file,
    )
    # Testphase standardmäßig als abgelaufen vormerken, damit die Gratis-Stufe
    # (Nutzungskontingent) in den Tests greift und nicht die zeitbasierte
    # Testphase Premium freischaltet. Tests der Testphase setzen dies gezielt um.
    usage_file.write_text(
        json.dumps({"trial_start": "2000-01-01T00:00:00"}), encoding="utf-8"
    )


@pytest.fixture(autouse=True)
def _pin_automatic_language(monkeypatch):
    """
    Legt die Sprache für ``language="automatic"`` deterministisch auf Deutsch.

    Viele UI-Tests prüfen den deutschen Anzeigetext. Ohne diese Fixierung
    haengt ``automatic`` am System-Locale der Maschine: lokal (DE) gruen, auf
    dem CI-Runner (EN) rot. Das Pinnen macht die Testsuite locale-unabhaengig.
    Tests mit explizitem ``language=`` (z. B. "en") sind davon unberuehrt. Die
    tatsaechliche Locale-Erkennung wird separat geprueft (siehe
    ``test_language_detection_v086a26.py``), damit diese Fixierung dort keine
    echten Fehler verdecken kann.
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
