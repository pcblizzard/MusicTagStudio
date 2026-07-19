from musictagstudio.lyrics import LyricsDocument, LyricsLine, load_sidecar, save_sidecar


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
