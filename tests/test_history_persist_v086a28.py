from __future__ import annotations

from musictagstudio.history import HistoryManager


def _manager(tmp_path, store):
    def read_state(path):
        tags, cover = store[path]
        return dict(tags), cover

    def write_state(path, tags, cover):
        store[path] = (dict(tags), cover)

    return HistoryManager(
        tmp_path, read_state=read_state, write_state=write_state
    )


def _real_file(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"x")
    return str(path.resolve())


def test_undo_persists_across_restart(tmp_path):
    key = _real_file(tmp_path, "song.flac")
    store = {key: ({"title": "Alt"}, None)}
    history = _manager(tmp_path, store)
    entry = history.begin("Tags", [key])
    store[key] = ({"title": "Neu"}, None)
    history.commit(entry)

    # „Neustart": frischer Manager auf demselben Verzeichnis.
    reopened = _manager(tmp_path, store)
    assert reopened.can_undo
    reopened.undo()
    assert store[key][0]["title"] == "Alt"  # Undo aus vorheriger Sitzung


def test_uncommitted_entries_not_loaded(tmp_path):
    key = _real_file(tmp_path, "song.flac")
    store = {key: ({"title": "Alt"}, None)}
    history = _manager(tmp_path, store)
    history.begin("Abgebrochen", [key])  # kein commit

    reopened = _manager(tmp_path, store)
    assert not reopened.can_undo


def test_describe_changes_lists_field_diff(tmp_path):
    key = _real_file(tmp_path, "song.flac")
    store = {key: ({"title": "Alt", "artist": "A"}, None)}
    history = _manager(tmp_path, store)
    entry = history.begin("Tags", [key])
    store[key] = ({"title": "Neu", "artist": "A"}, None)
    committed = history.commit(entry)

    changes = history.describe_changes(committed)
    assert len(changes) == 1
    assert changes[0].field_changes == (("title", "Alt", "Neu"),)


def test_describe_changes_reports_rename(tmp_path):
    history = _manager(tmp_path, {})
    entry = history.commit_rename("Umbenennen", [("old.flac", "new.flac")])
    changes = history.describe_changes(entry)
    assert changes[0].rename == ("old.flac", "new.flac")
