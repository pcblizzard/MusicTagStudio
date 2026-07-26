from __future__ import annotations

import os
from datetime import date
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from musictagstudio.direct_album_lookup import is_prerelease_date


TODAY = date(2026, 7, 26)


def test_future_day_precise_date_is_prerelease():
    assert is_prerelease_date("2026-10-01T07:00:00Z", TODAY) is True
    assert is_prerelease_date("2026-10-01", TODAY) is True


def test_year_only_is_not_prerelease():
    # Reines Jahr ist zu unsicher (Platzhalter) -> keine Vorab-Kennzeichnung.
    assert is_prerelease_date("2026", TODAY) is False
    assert is_prerelease_date("", TODAY) is False


def test_past_and_today_are_not_prerelease():
    assert is_prerelease_date("2018-09-21T07:00:00Z", TODAY) is False
    assert is_prerelease_date("2026-07-26", TODAY) is False  # heute zählt nicht


def test_track_display_marks_unreleased_tracks():
    from musictagstudio.ui.direct_album_dialog import DirectAlbumDialog

    released = SimpleNamespace(title="Keine Angst", is_streamable=True)
    placeholder = SimpleNamespace(title="Track 2", is_streamable=False)

    assert DirectAlbumDialog._track_display(released) == "Keine Angst"
    assert (
        DirectAlbumDialog._track_display(placeholder)
        == "Track 2 · noch nicht veröffentlicht"
    )


def test_prerelease_note_only_for_future_date():
    from musictagstudio.ui.direct_album_dialog import DirectAlbumDialog

    future = SimpleNamespace(release_date="2999-01-01T00:00:00Z")
    year_only = SimpleNamespace(release_date="2026")

    assert "Vorabveröffentlichung" in DirectAlbumDialog._prerelease_note(future)
    assert DirectAlbumDialog._prerelease_note(year_only) == ""


def test_placeholder_title_detection():
    from musictagstudio.ui.media_library_widget import _is_placeholder_title

    assert _is_placeholder_title("Track 2") is True
    assert _is_placeholder_title("Track  11") is True
    assert _is_placeholder_title("track12") is True
    assert _is_placeholder_title("Keine Angst") is False
    assert _is_placeholder_title("Soundtrack 2") is False
    assert _is_placeholder_title("") is False


def test_localized_date_formats_full_date_and_falls_back():
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from musictagstudio.ui.formatting import localized_date

    formatted = localized_date("2026-10-01T07:00:00Z")
    # Tagesgenaues Datum -> lokalisierte, nicht-leere Ausgabe mit Jahr.
    assert "2026" in formatted or "26" in formatted
    assert formatted != "2026-10-01T07:00:00Z"
    # Reines Jahr/ungültig -> Rohwert (max. 10 Zeichen) als Fallback.
    assert localized_date("2026") == "2026"
    assert localized_date("") == ""


def test_direct_album_track_defaults_streamable():
    from musictagstudio.direct_album_lookup import DirectAlbumTrack

    track = DirectAlbumTrack(
        title="T", artist="A", album_artist="A", album="X", genre="",
        year="2022", track="1", total_tracks="1", disc="1", total_discs="1",
    )
    assert track.is_streamable is True
