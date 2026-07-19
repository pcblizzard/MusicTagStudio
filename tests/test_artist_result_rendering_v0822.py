import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from musictagstudio.media_library.controller import ArtistSearchResponse
from musictagstudio.media_library.client import RequestTrace
from musictagstudio.media_library.service import ArtistCandidate
from musictagstudio.ui.media_library_widget import (
    MediaLibraryWidget,
    _artist_text,
)


def candidate() -> ArtistCandidate:
    return ArtistCandidate(
        artist_id="abc",
        name="Stieber Twins",
        sort_name="Stieber Twins",
        disambiguation="German hip-hop group",
        country="DE",
        artist_type="Group",
        score=100,
    )


def test_artist_text_contains_name_and_details():
    text = _artist_text(
        candidate()
    )

    assert "Stieber Twins" in text
    assert "DE" in text
    assert "Group" in text
    assert "German hip-hop group" in text


def test_loaded_artist_is_rendered_in_result_list():
    app = (
        QApplication.instance()
        or QApplication([])
    )
    widget = MediaLibraryWidget()

    response = ArtistSearchResponse(
        query="Stieber Twins",
        artists=(
            candidate(),
        ),
        exact_match=True,
        suggestion_mode=False,
        traces=(
            RequestTrace(
                url="https://musicbrainz.org/ws/2/artist",
                status="200 OK",
                elapsed_ms=10,
                result_count=1,
            ),
        ),
    )

    widget._artists_loaded(
        response
    )

    assert widget.artist_list.count() == 1
    assert "Stieber Twins" in widget.artist_list.item(0).text()
    widget.close()
