import json

from musictagstudio.history import HistoryManager


def _manager(tmp_path, store, max_entries=50):
    """HistoryManager mit In-Memory-Zustand statt echter Audio-I/O."""

    def read_state(path):
        tags, cover = store[path]
        return dict(tags), cover

    def write_state(path, tags, cover):
        store[path] = (dict(tags), cover)

    return HistoryManager(
        tmp_path,
        read_state=read_state,
        write_state=write_state,
        max_entries=max_entries,
    )


def _real_file(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"x")  # muss existieren; Inhalt egal (I/O ist injiziert)
    return str(path.resolve())


def test_undo_and_redo_restore_tags(tmp_path):
    key = _real_file(tmp_path, "song.flac")
    store = {key: ({"title": "Alt", "artist": "A"}, None)}
    history = _manager(tmp_path, store)

    entry = history.begin("Tags ändern", [key])
    store[key] = ({"title": "Neu", "artist": "A"}, None)  # simuliertes Schreiben
    history.commit(entry)

    history.undo()
    assert store[key][0]["title"] == "Alt"

    history.redo()
    assert store[key][0]["title"] == "Neu"


def test_rollback_pending_restores_before(tmp_path):
    key = _real_file(tmp_path, "song.flac")
    store = {key: ({"title": "Original"}, None)}
    history = _manager(tmp_path, store)

    entry = history.begin("Fehlerhafter Vorgang", [key])
    store[key] = ({"title": "Halbfertig"}, None)
    history.rollback_pending(entry)

    assert store[key][0]["title"] == "Original"
    assert history.can_undo is False  # nicht committet -> nicht im Stack


def test_cover_undo_restores_previous_cover(tmp_path):
    key = _real_file(tmp_path, "song.flac")
    store = {key: ({"title": "T"}, b"ALTES_COVER")}
    history = _manager(tmp_path, store)

    entry = history.begin("Cover geändert", [key])
    store[key] = ({"title": "T"}, b"NEUES_COVER")
    history.commit(entry)

    history.undo()
    assert store[key][1] == b"ALTES_COVER"
    history.redo()
    assert store[key][1] == b"NEUES_COVER"


def test_no_full_file_copies_are_stored(tmp_path):
    # Der Verlauf darf keine großen Dateikopien mehr anlegen.
    key = _real_file(tmp_path, "big.wv")
    store = {key: ({"title": "T"}, b"cover")}
    history = _manager(tmp_path, store)
    entry = history.begin("Tags", [key])
    history.commit(entry)

    root = tmp_path / ".musictagstudio" / "history"
    total = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    # Nur JSON-Snapshots + ein kleiner Cover-Blob – weit unter 1 MB.
    assert total < 100_000


def test_identical_cover_is_deduplicated(tmp_path):
    keys = [_real_file(tmp_path, f"{i:02d}.flac") for i in range(5)]
    cover = b"SAME_COVER_BYTES"
    store = {k: ({"title": f"T{i}"}, cover) for i, k in enumerate(keys)}
    history = _manager(tmp_path, store)

    entry = history.begin("Cover für Album", keys)
    history.commit(entry)

    blobs = list((tmp_path / ".musictagstudio" / "history" / "blobs").glob("*"))
    # Fünf Titel mit identischem Cover -> genau ein Blob.
    assert len(blobs) == 1


def test_prune_keeps_only_recent_entries_on_start(tmp_path):
    # Fünf alte Vorgänge früherer Sitzungen auf der Platte.
    root = tmp_path / ".musictagstudio" / "history"
    blobs = root / "blobs"
    blobs.mkdir(parents=True)
    for i in range(5):
        entry = root / f"2020010{i}-000000-{i:08d}"
        entry.mkdir()
        digest = f"hash{i}"
        (blobs / digest).write_bytes(b"c")
        (entry / "before.json").write_text(
            json.dumps([{"path": "x", "tags": {}, "cover": digest}]),
            encoding="utf-8",
        )

    # Neuer Manager mit Deckel 3 räumt beim Start auf.
    _manager(tmp_path, {}, max_entries=3)

    remaining = sorted(
        p.name for p in root.iterdir() if p.is_dir() and p.name != "blobs"
    )
    assert remaining == [
        "20200102-000000-00000002",
        "20200103-000000-00000003",
        "20200104-000000-00000004",
    ]
    # Verwaiste Blobs der gelöschten Einträge werden mit aufgeräumt.
    assert sorted(p.name for p in blobs.iterdir()) == ["hash2", "hash3", "hash4"]


def test_active_session_entries_are_never_pruned(tmp_path):
    # Deckel 1, aber drei Vorgänge ohne Undo -> alle noch aktiv -> bleiben.
    store = {}
    history = _manager(tmp_path, store, max_entries=1)
    for i in range(3):
        key = _real_file(tmp_path, f"{i}.flac")
        store[key] = ({"title": str(i)}, None)
        history.commit(history.begin("op", [key]))

    root = tmp_path / ".musictagstudio" / "history"
    dirs = [p for p in root.iterdir() if p.is_dir() and p.name != "blobs"]
    assert len(dirs) == 3  # aktive Einträge werden trotz Deckel geschützt
