from __future__ import annotations

from PySide6.QtWidgets import QApplication

from musictagstudio.batch_comparison_logic import BatchSongProposal
from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song
from musictagstudio.ui import batch_dialog
from musictagstudio.ui.batch_dialog import BatchComparisonDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _dialog(song: Song, candidate: MetadataCandidate) -> BatchComparisonDialog:
    proposal = BatchSongProposal(
        song_row=0,
        song=song,
        candidates=[candidate],
        warnings=[],
    )
    return BatchComparisonDialog(
        [proposal],
        primary_source="apple_music",
        feature_handling="artist_only",
    )


def test_save_without_changes_informs_and_does_not_accept(monkeypatch):
    _app()
    shown = []
    monkeypatch.setattr(
        batch_dialog.QMessageBox,
        "information",
        lambda *args, **kwargs: shown.append(args[1:3]),
    )

    # Local already matches the Apple candidate -> nothing to write.
    song = Song(title="Cool", artist="Danger Dan", album="Album", track="1")
    candidate = MetadataCandidate(
        source="apple_music",
        confidence=100,
        title="Cool",
        artist="Danger Dan",
        album="Album",
        track="1",
    )
    dialog = _dialog(song, candidate)

    dialog._accept_selection()

    assert dialog.selected_updates == {}
    assert shown, "a message should inform the user that nothing changed"
    assert dialog.result() != BatchComparisonDialog.DialogCode.Accepted
    dialog.deleteLater()


def test_save_with_changes_accepts(monkeypatch):
    _app()
    monkeypatch.setattr(
        batch_dialog.QMessageBox,
        "information",
        lambda *args, **kwargs: None,
    )

    song = Song(title="Cool", artist="Danger Dan", album="Altes Album", track="1")
    candidate = MetadataCandidate(
        source="apple_music",
        confidence=100,
        title="Cool",
        artist="Danger Dan",
        album="Neues Album",
        track="1",
    )
    dialog = _dialog(song, candidate)

    dialog._accept_selection()

    assert dialog.selected_updates
    assert dialog.result() == BatchComparisonDialog.DialogCode.Accepted
    dialog.deleteLater()
