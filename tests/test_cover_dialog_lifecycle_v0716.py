from pathlib import Path


def source_text() -> str:
    path = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "cover_dialog.py"
    )

    return path.read_text(
        encoding="utf-8"
    )


def test_dialog_uses_owned_thread_pool_and_retains_workers():
    text = source_text()

    assert "QThreadPool(self)" in text
    assert "self._active_workers" in text
    assert "def _start_worker" in text


def test_preview_callbacks_are_bound_slots():
    text = source_text()

    assert "def _preview_finished" in text
    assert "def _preview_failed" in text
    assert "worker.signals.finished.connect(\n            self._preview_finished" in text


def test_close_invalidates_background_callbacks():
    text = source_text()

    assert "def _prepare_close" in text
    assert "self._closing = True" in text
    assert "self._preview_generation += 1" in text


def test_prefetch_is_bounded():
    text = source_text()

    assert "for row in rows[:3]" in text
