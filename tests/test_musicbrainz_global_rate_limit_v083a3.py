from pathlib import Path

from musictagstudio import musicbrainz_http
from musictagstudio import __version__


def test_musicbrainz_identity_uses_current_version():
    assert f"MusicTagStudio/{__version__}" in (
        musicbrainz_http.MUSICBRAINZ_USER_AGENT
    )
    assert "github.com/pcblizzard/MusicTagStudio" in (
        musicbrainz_http.MUSICBRAINZ_USER_AGENT
    )


def test_all_musicbrainz_http_paths_use_the_shared_slot():
    root = Path(__file__).parents[1] / "src" / "musictagstudio"
    files = (
        root / "media_library" / "client.py",
        root / "providers" / "musicbrainz.py",
        root / "direct_album_lookup.py",
        root / "cover_management" / "providers.py",
    )

    for path in files:
        assert "wait_for_musicbrainz_slot" in path.read_text(encoding="utf-8")
