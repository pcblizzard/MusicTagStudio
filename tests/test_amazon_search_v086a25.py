from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from musictagstudio.ui.media_library_widget import MediaLibraryWidget, _amazon_tld


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_amazon_tld_maps_countries():
    assert _amazon_tld("DE") == "de"
    assert _amazon_tld("AT") == "de"
    assert _amazon_tld("US") == "com"
    assert _amazon_tld("GB") == "co.uk"
    assert _amazon_tld("") == "de"  # Standard
    assert _amazon_tld("XX") == "de"  # unbekannt -> Standard


def test_search_amazon_opens_query_with_artist_and_album(monkeypatch):
    _app()
    widget = MediaLibraryWidget()
    widget.current_group = SimpleNamespace(
        title="12 Runden", artist="Kontra K", release_group_id="x"
    )

    opened: list[str] = []
    monkeypatch.setattr(
        "musictagstudio.ui.media_library_widget.webbrowser.open",
        lambda url: opened.append(url),
    )

    widget._search_amazon()

    assert len(opened) == 1
    url = opened[0]
    assert url.startswith("https://www.amazon.")
    assert "/s?" in url
    assert "k=Kontra+K+12+Runden" in url
    widget.deleteLater()


def test_search_amazon_falls_back_to_current_artist(monkeypatch):
    # Veröffentlichung ohne eigenen Künstlernamen -> Künstler-Kontext nutzen.
    _app()
    widget = MediaLibraryWidget()
    widget.current_artist_name = "Danger Dan"
    widget.current_group = SimpleNamespace(
        title="Keine Angst", artist="", release_group_id="x"
    )

    opened: list[str] = []
    monkeypatch.setattr(
        "musictagstudio.ui.media_library_widget.webbrowser.open",
        lambda url: opened.append(url),
    )

    widget._search_amazon()
    assert opened and "k=Danger+Dan+Keine+Angst" in opened[0]
    widget.deleteLater()


def test_search_amazon_without_group_is_noop(monkeypatch):
    _app()
    widget = MediaLibraryWidget()
    widget.current_group = None

    opened: list[str] = []
    monkeypatch.setattr(
        "musictagstudio.ui.media_library_widget.webbrowser.open",
        lambda url: opened.append(url),
    )

    widget._search_amazon()
    assert opened == []
    widget.deleteLater()
