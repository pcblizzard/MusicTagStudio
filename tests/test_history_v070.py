from musictagstudio.history import (
    HistoryManager,
)


def test_undo_and_redo_restore_file(
    tmp_path,
):
    target = tmp_path / "song.flac"
    target.write_bytes(b"before")
    history = HistoryManager(
        tmp_path
    )
    entry = history.begin(
        "Test",
        [str(target)],
    )
    target.write_bytes(b"after")
    history.commit(entry)

    history.undo()
    assert target.read_bytes() == b"before"

    history.redo()
    assert target.read_bytes() == b"after"
