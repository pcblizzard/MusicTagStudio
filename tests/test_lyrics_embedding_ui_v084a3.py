from pathlib import Path


def test_lyrics_dialog_requires_preview_before_embedding():
    source = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "lyrics_dialog.py"
    ).read_text(encoding="utf-8")

    # Einbetten-Button ist jetzt i18n-basiert (tr("embed_in_audio")).
    assert 'tr("embed_in_audio", language)' in source
    assert "LyricsEmbedPreviewDialog" in source
    assert "Bestehende eingebettete Lyrics werden ersetzt" in source
    assert "confirmed=True" in source
    assert '"Ctrl+L"' in source
    assert '"Ctrl+S"' in source
    assert '"Ctrl+E"' in source
