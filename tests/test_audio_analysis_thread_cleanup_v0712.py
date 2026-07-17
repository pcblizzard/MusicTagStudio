from pathlib import Path


def source_text() -> str:
    path = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "audio_analysis_dialog.py"
    )

    return path.read_text(encoding="utf-8")


def test_close_event_uses_safe_thread_check():
    text = source_text()

    assert "def _thread_is_running" in text
    assert "except RuntimeError" in text
    assert "self.thread = None" in text


def test_finished_thread_reference_is_cleared():
    text = source_text()

    assert "def _clear_finished_thread" in text
    assert "current_thread.finished.connect" in text
