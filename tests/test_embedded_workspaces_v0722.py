from pathlib import Path


def source(name: str) -> str:
    return (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / name
    ).read_text(encoding="utf-8")


def test_main_window_embeds_real_tools():
    text = source("main_window.py")

    assert "self.audio_analysis_workspace = AudioAnalysisDialog" in text
    assert "self.library_audit_workspace = LibraryAuditDialog" in text
    assert "self.settings_workspace = SettingsDialog" in text
    assert '"Audio-Analyse öffnen"' not in text
    assert '"Bibliotheksprüfung öffnen"' not in text
    assert '"Einstellungen öffnen"' not in text


def test_dialogs_support_embedded_mode():
    assert "embedded: bool = False" in source("audio_analysis_dialog.py")
    assert "def set_songs" in source("audio_analysis_dialog.py")
    assert "embedded: bool = False" in source("library_audit_dialog.py")
    assert "def set_songs" in source("library_audit_dialog.py")
    assert "embedded: bool = False" in source("settings_dialog.py")
    assert "def _save_embedded" in source("settings_dialog.py")
