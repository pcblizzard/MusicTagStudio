from musictagstudio.cover_management.manager import (
    CoverManager,
)
from musictagstudio.cover_management.models import (
    CoverCandidate,
)
from musictagstudio.settings import AppSettings
from musictagstudio.cover_management import manager


def test_preview_is_downloaded_only_once(
    monkeypatch,
    tmp_path,
):
    CoverManager._preview_cache.clear()
    calls = []

    monkeypatch.setattr(
        manager,
        "download",
        lambda url, timeout=15: (
            calls.append(
                (url, timeout)
            )
            or b"preview"
        ),
    )
    settings = AppSettings()
    cover_manager = CoverManager(
        settings
    )
    candidate = CoverCandidate(
        source="apple_music",
        source_label="Apple Music",
        url="https://example.test/original.jpg",
        preview_url="https://example.test/preview.jpg",
    )

    assert (
        cover_manager.load_preview(
            candidate
        )
        == b"preview"
    )
    assert (
        cover_manager.load_preview(
            candidate
        )
        == b"preview"
    )
    assert calls == [
        (
            "https://example.test/preview.jpg",
            8,
        )
    ]
