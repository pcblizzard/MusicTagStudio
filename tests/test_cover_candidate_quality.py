from musictagstudio.cover_management.models import (
    CoverCandidate,
)


def test_quality_summary():
    candidate = CoverCandidate(
        source="apple_music",
        source_label="Apple Music",
        url="https://example.test/cover.jpg",
        width=3000,
        height=3000,
        mime="image/jpeg",
        file_size=2_500_000,
    )

    assert "3000 × 3000" in candidate.quality_summary
    assert "image/jpeg" in candidate.quality_summary
    assert "quadratisch" in candidate.quality_summary
    assert "MB" in candidate.quality_summary
