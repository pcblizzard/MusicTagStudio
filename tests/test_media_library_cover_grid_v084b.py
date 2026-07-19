import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from musictagstudio.media_library.service import ReleaseGroup
from musictagstudio.media_library import tasks
from musictagstudio.ui import media_library_widget as widget_module
from musictagstudio.ui.media_library_widget import MediaLibraryWidget


def musicbrainz_group() -> ReleaseGroup:
    return ReleaseGroup(
        release_group_id="13b2e709-4136-4024-8c4e-a5bfef92a948",
        title="Learning English: Lesson 2",
        first_release_date="2017-05-05",
        primary_type="Album",
        artist="Die Toten Hosen",
        source="musicbrainz",
    )


def test_cover_grid_loads_musicbrainz_release_group_cover():
    app = QApplication.instance() or QApplication([])
    widget = MediaLibraryWidget()
    calls = []

    widget._run = lambda function, *args, **kwargs: calls.append(
        (function, args, kwargs)
    )
    widget._load_release_thumbnail(0, musicbrainz_group())

    assert len(calls) == 1
    function, args, _ = calls[0]
    assert function is widget_module._fetch_release_group_cover_with_discogs
    assert args[0] == "13b2e709-4136-4024-8c4e-a5bfef92a948"
    assert args[2] == "Die Toten Hosen"
    assert args[3] == "Learning English: Lesson 2"
    assert args[4] == "2017"


def test_late_thumbnail_is_not_applied_to_a_different_release(monkeypatch):
    app = QApplication.instance() or QApplication([])
    widget = MediaLibraryWidget()
    widget.release_groups = [musicbrainz_group()]

    def unexpected_pixmap():
        raise AssertionError("obsolete thumbnail was rendered")

    monkeypatch.setattr(widget_module, "QPixmap", unexpected_pixmap)
    widget._apply_release_thumbnail(0, b"not-an-image", "different-id")


def test_release_group_cover_uses_discogs_only_after_archive_miss(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tasks,
        "_fetch_release_group_cover",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        tasks,
        "_fetch_matching_discogs_cover",
        lambda *args: calls.append(args) or b"discogs-cover",
    )

    result = tasks._fetch_release_group_cover_with_discogs(
        "group-id",
        widget_module.Path("cache"),
        "Die Toten Hosen",
        "Schön sein",
        "1999",
        "token",
    )

    assert result == b"discogs-cover"
    assert len(calls) == 1


def test_release_group_cover_does_not_spend_discogs_request_on_archive_hit(
    monkeypatch,
):
    monkeypatch.setattr(
        tasks,
        "_fetch_release_group_cover",
        lambda *_args: b"archive-cover",
    )
    monkeypatch.setattr(
        tasks,
        "_fetch_matching_discogs_cover",
        lambda *_args: (_ for _ in ()).throw(AssertionError()),
    )

    result = tasks._fetch_release_group_cover_with_discogs(
        "group-id",
        widget_module.Path("cache"),
        "Die Toten Hosen",
        "Schön sein",
        "1999",
        "token",
    )

    assert result == b"archive-cover"
