from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song
from musictagstudio.services import proposal


def _song() -> Song:
    return Song(
        title="Titel",
        artist="Danger Dan",
        album="Album",
        track="1",
        path="C:/Album/1.flac",
    )


def _hit(store: str) -> MetadataCandidate:
    return MetadataCandidate(
        source="apple_music",
        confidence=95,
        title="Titel",
        artist="Danger Dan",
        album="Album",
        track="1",
        external_id=f"song-{store}",
    )


def _record_stores(monkeypatch, results_by_store):
    stores: list[str] = []

    def fake_search(*args, **kwargs):
        store = kwargs["country"]
        stores.append(store)
        return results_by_store.get(store, [])

    monkeypatch.setattr(proposal, "search_apple", fake_search)
    monkeypatch.setattr(proposal, "_local_duration_ms", lambda p: None)
    monkeypatch.setattr(proposal, "_title_from_filename", lambda p: "")
    return stores


def test_only_primary_store_queried_when_it_has_results(monkeypatch):
    stores = _record_stores(monkeypatch, {"DE": [_hit("DE")]})
    candidates: list[MetadataCandidate] = []

    proposal._add_safe_single_apple_candidate(
        _song(),
        candidates,
        [],
        country="DE",
    )

    assert stores == ["DE"]
    assert len(candidates) == 1


def test_us_store_queried_only_when_primary_empty(monkeypatch):
    stores = _record_stores(monkeypatch, {"US": [_hit("US")]})
    candidates: list[MetadataCandidate] = []

    proposal._add_safe_single_apple_candidate(
        _song(),
        candidates,
        [],
        country="DE",
    )

    assert stores == ["DE", "US"]
    assert len(candidates) == 1
