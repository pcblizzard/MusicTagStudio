from musictagstudio.lyrics import LyricsDocument, LyricsLine, load_sidecar, save_sidecar
import pytest


def test_sidecar_is_saved_next_to_audio_file(tmp_path):
    audio = tmp_path / "Titel.flac"
    document = LyricsDocument(
        synced_lines=(LyricsLine(500, "Start"),),
        source="LRCLIB",
    )

    destination = save_sidecar(audio, document)
    restored = load_sidecar(audio)

    assert destination == tmp_path / "Titel.lrc"
    assert destination.read_bytes().startswith(b"[00:00.50]Start")
    assert restored is not None
    assert restored.synced_lines == document.synced_lines


def test_empty_lyrics_do_not_overwrite_existing_sidecar(tmp_path):
    audio = tmp_path / "Titel.flac"
    sidecar = tmp_path / "Titel.lrc"
    sidecar.write_text("Vorhanden", encoding="utf-8")

    with pytest.raises(ValueError, match="Leere Lyrics"):
        save_sidecar(audio, LyricsDocument())

    assert sidecar.read_text(encoding="utf-8") == "Vorhanden"
