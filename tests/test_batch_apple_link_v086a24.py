from __future__ import annotations

from PySide6.QtWidgets import QApplication

from musictagstudio.batch_comparison_logic import BatchSongProposal
from musictagstudio.direct_album_lookup import (
    DirectAlbumResult,
    DirectAlbumTrack,
)
from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song
from musictagstudio.ui.batch_dialog import BatchComparisonDialog


ALBUM = "Dinkelbrot & Ölsardinen"
APPLE_WARNING = (
    "Kein ausreichend sicherer Apple-Treffer. „Cool“ wurde wegen nur "
    "8 % Sicherheit nicht übernommen."
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _proposal(row: int, title: str, track: str) -> BatchSongProposal:
    song = Song(
        title=title,
        artist="Danger Dan",
        album_artist="Danger Dan",
        album=ALBUM,
        track=track,
        path=f"C:/Album/{track}.flac",
    )
    mb = MetadataCandidate(
        source="musicbrainz",
        confidence=90,
        title=title,
        artist="Danger Dan",
        album=ALBUM,
        track=track,
    )
    return BatchSongProposal(
        song_row=row,
        song=song,
        candidates=[mb],
        warnings=[APPLE_WARNING],
    )


def _album_result() -> DirectAlbumResult:
    tracks = tuple(
        DirectAlbumTrack(
            title=title,
            artist="Danger Dan",
            album_artist="Danger Dan",
            album=ALBUM,
            genre="Hip-Hop/Rap",
            year="2012",
            track=str(number),
            total_tracks="2",
            disc="1",
            total_discs="1",
        )
        for number, title in enumerate(["Ölsardinenindustrie", "Cool"], start=1)
    )
    return DirectAlbumResult(
        provider="apple_music",
        album=ALBUM,
        album_artist="Danger Dan",
        tracks=tracks,
    )


def test_apple_link_injects_candidates_and_rebuilds():
    _app()
    proposals = [
        _proposal(0, "Ölsardinenindustrie", "1"),
        _proposal(1, "Cool", "2"),
    ]
    dialog = BatchComparisonDialog(
        proposals,
        primary_source="apple_music",
        feature_handling="artist_only",
    )

    # The low-confidence Apple warning must have created the link row.
    assert hasattr(dialog, "_apple_link_button")

    dialog._on_apple_album_loaded("1603274418", _album_result())

    for proposal, expected_track in zip(proposals, ("1", "2")):
        apple = [
            candidate
            for candidate in proposal.candidates
            if candidate.source == "apple_music"
        ]
        assert len(apple) == 1
        assert apple[0].track == expected_track
        assert apple[0].release_id == "1603274418"

    assert "2 von 2" in dialog._apple_link_status.text()
    dialog.deleteLater()


def test_apple_link_row_absent_without_apple_warning():
    _app()
    proposal = BatchSongProposal(
        song_row=0,
        song=Song(title="Cool", album=ALBUM),
        candidates=[],
        warnings=[],
    )
    dialog = BatchComparisonDialog(
        [proposal],
        primary_source="musicbrainz",
        feature_handling="artist_only",
    )

    assert not hasattr(dialog, "_apple_link_button")
    dialog.deleteLater()


def test_apple_link_row_shown_when_apple_preferred_but_empty():
    # Kein Apple-Kandidat und keine Warnung (Fix #1 unterdrückt sie),
    # aber Apple ist bevorzugte Quelle -> Feld muss erscheinen.
    _app()
    proposal = BatchSongProposal(
        song_row=0,
        song=Song(title="Cool", album=ALBUM, track="2"),
        candidates=[
            MetadataCandidate(
                source="musicbrainz",
                confidence=90,
                title="Cool",
                album=ALBUM,
                track="2",
            )
        ],
        warnings=[],
    )
    dialog = BatchComparisonDialog(
        [proposal],
        primary_source="apple_music",
        feature_handling="artist_only",
    )

    assert hasattr(dialog, "_apple_link_button")
    dialog.deleteLater()
