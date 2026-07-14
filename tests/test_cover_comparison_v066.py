from musictagstudio.cover_management.comparison import (
    compare_cover_candidates,
    md5_bytes,
    quality_score,
)
from musictagstudio.cover_management.models import (
    CoverCandidate,
)


def test_identical_cover_hash():
    left = CoverCandidate(
        source="local",
        source_label="Lokal",
        url="file:///a.jpg",
        width=1000,
        height=1000,
        md5="abc",
    )
    right = CoverCandidate(
        source="apple_music",
        source_label="Apple Music",
        url="https://example.test/a.jpg",
        width=3000,
        height=3000,
        md5="abc",
    )

    result = compare_cover_candidates(
        left,
        right,
    )

    assert result.relationship == "identical"


def test_same_dimensions_different_content():
    left = CoverCandidate(
        source="local",
        source_label="Lokal",
        url="file:///a.jpg",
        width=1000,
        height=1000,
        md5="abc",
    )
    right = CoverCandidate(
        source="apple_music",
        source_label="Apple Music",
        url="https://example.test/b.jpg",
        width=1000,
        height=1000,
        md5="def",
    )

    result = compare_cover_candidates(
        left,
        right,
    )

    assert result.relationship == "same_dimensions"


def test_quality_score_prefers_large_square_image():
    large_square = quality_score(
        width=3000,
        height=3000,
        mime="image/jpeg",
        file_size=2_000_000,
    )
    small_non_square = quality_score(
        width=500,
        height=400,
        mime="image/jpeg",
        file_size=100_000,
    )

    assert large_square > small_non_square


def test_md5_bytes_is_stable():
    assert md5_bytes(b"cover") == md5_bytes(
        b"cover"
    )
