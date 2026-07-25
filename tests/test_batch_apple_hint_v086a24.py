from musictagstudio.batch_comparison_logic import BatchSongProposal
from musictagstudio.models.song import Song
from musictagstudio.ui.batch_dialog import apple_link_hint_needed


def _proposal(warnings: list[str]) -> BatchSongProposal:
    return BatchSongProposal(
        song_row=0,
        song=Song(title="Titel", album="Album"),
        candidates=[],
        warnings=warnings,
    )


def test_hint_for_low_confidence_apple_warning():
    proposals = [
        _proposal(
            [
                "Kein ausreichend sicherer Apple-Treffer. "
                "„Titel“ wurde wegen nur 8 % Sicherheit nicht übernommen."
            ]
        )
    ]
    assert apple_link_hint_needed(proposals) is True


def test_hint_for_unmatched_apple_album_track():
    proposals = [
        _proposal(
            [
                "Apple Music: Dieser Titel konnte der vollständigen "
                "Albumtrackliste nicht sicher zugeordnet werden."
            ]
        )
    ]
    assert apple_link_hint_needed(proposals) is True


def test_no_hint_for_musicbrainz_only_warning():
    proposals = [
        _proposal(
            [
                "MusicBrainz: Dieser Titel konnte der vollständigen "
                "Albumtrackliste nicht sicher zugeordnet werden."
            ]
        )
    ]
    assert apple_link_hint_needed(proposals) is False


def test_no_hint_without_warnings():
    assert apple_link_hint_needed([_proposal([])]) is False
