from pathlib import Path

from musictagstudio.cover_management.cache import (
    CoverSearchCache,
)
from musictagstudio.cover_management.models import (
    CoverCandidate,
)


def test_cache_roundtrip(tmp_path: Path):
    cache = CoverSearchCache(
        tmp_path / "cover_search.json"
    )
    candidate = CoverCandidate(
        source="apple_music",
        source_label="Apple Music",
        url="https://example.test/original.jpg",
        preview_url="https://example.test/preview.jpg",
        width=3000,
        height=3000,
        mime="image/jpeg",
        release_id="123",
        score=95,
        album="Album",
        artist="Artist",
    )

    cache.put(
        "artist|album",
        [candidate],
    )
    result = cache.get(
        "artist|album"
    )

    assert result is not None
    assert len(result) == 1
    assert result[0].release_id == "123"
    assert result[0].data is None


def test_local_candidate_is_not_persisted(
    tmp_path: Path,
):
    cache = CoverSearchCache(
        tmp_path / "cover_search.json"
    )
    local = CoverCandidate(
        source="local",
        source_label="Lokal",
        url="file:///cover.jpg",
        data=b"cover",
        is_local=True,
    )

    cache.put(
        "local",
        [local],
    )

    assert cache.get("local") == []


def test_clear_removes_cache_file(
    tmp_path: Path,
):
    path = tmp_path / "cover_search.json"
    cache = CoverSearchCache(path)
    cache.put(
        "key",
        [
            CoverCandidate(
                source="apple_music",
                source_label="Apple Music",
                url="https://example.test/cover.jpg",
            )
        ],
    )

    assert path.exists()

    cache.clear()

    assert not path.exists()
