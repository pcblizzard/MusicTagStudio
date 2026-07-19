import json
import pytest

from musictagstudio import __version__
from musictagstudio.lyrics.lrclib import LrclibClient, document_from_lrclib


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(
            {
                "id": 42,
                "trackName": "Maske",
                "artistName": "Sido",
                "albumName": "Maske",
                "plainLyrics": "Hallo",
                "syncedLyrics": "[00:01.00]Hallo",
                "instrumental": False,
            }
        ).encode()


def test_lrclib_response_becomes_lyrics_document():
    document = document_from_lrclib(
        {
            "id": 42,
            "trackName": "Maske",
            "artistName": "Sido",
            "albumName": "Maske",
            "plainLyrics": "Hallo",
            "syncedLyrics": "[00:01.00]Hallo",
        }
    )

    assert document.provider_id == "42"
    assert document.plain_text == "Hallo"
    assert document.synced_lines[0].time_ms == 1000


def test_lrclib_uses_cached_endpoint_by_default(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["user_agent"] = request.get_header("User-agent")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("musictagstudio.lyrics.lrclib.urlopen", fake_urlopen)
    document = LrclibClient().get(
        track_name="Maske",
        artist_name="Sido",
        album_name="Maske",
        duration=240,
    )

    assert "/api/get-cached?" in captured["url"]
    assert f"MusicTagStudio/{__version__}" in captured["user_agent"]
    assert document.source == "LRCLIB"


@pytest.mark.parametrize("duration", [0, -1, float("nan")])
def test_lrclib_rejects_invalid_duration(duration):
    with pytest.raises(ValueError, match="Titeldauer"):
        LrclibClient().get(
            track_name="Titel",
            artist_name="Künstler",
            album_name="Album",
            duration=duration,
        )
