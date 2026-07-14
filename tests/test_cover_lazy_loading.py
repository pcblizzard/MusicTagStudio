from musictagstudio.cover_management.models import (
    CoverCandidate,
)


def test_candidate_without_downloaded_data():
    candidate = CoverCandidate(
        source="apple_music",
        source_label="Apple Music",
        url="https://example.test/original.jpg",
        preview_url="https://example.test/preview.jpg",
        width=3000,
        height=3000,
    )

    assert candidate.data is None
    assert candidate.dimensions == "3000 × 3000"
