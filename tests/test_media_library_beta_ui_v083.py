import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from musictagstudio.ui.media_library_widget import (
    MediaLibraryWidget,
    _local_status_display,
)


def test_local_statuses_have_beta_symbols():
    assert _local_status_display("Lokal verfügbar") == "🟢 Lokal verfügbar"
    assert _local_status_display("Externe Quelle nicht erreichbar") == (
        "🟡 Externe Quelle nicht erreichbar"
    )
    assert _local_status_display("Nicht vorhanden") == "⚪ Nicht vorhanden"


def test_breadcrumb_path_and_artist_navigation():
    app = QApplication.instance() or QApplication([])
    widget = MediaLibraryWidget()
    searches = []
    widget.search_artist = lambda name, **kwargs: searches.append((name, kwargs))

    widget._push_breadcrumb("artist", "Aggro Berlin", "label-id")
    widget._push_breadcrumb("artist", "Sido", "artist-id")
    widget._push_breadcrumb("release", "Maske", "release-id")

    assert [entry[1] for entry in widget.breadcrumbs] == [
        "Aggro Berlin",
        "Sido",
        "Maske",
    ]
    assert "Aggro Berlin" in widget.breadcrumb_label.text()
    assert "Maske" in widget.breadcrumb_label.text()

    widget._breadcrumb_activated("breadcrumb:0")

    assert widget.breadcrumbs == [("artist", "Aggro Berlin", "label-id")]
    assert searches == [("Aggro Berlin", {"preserve_breadcrumbs": True})]
    widget.close()
    app.processEvents()
