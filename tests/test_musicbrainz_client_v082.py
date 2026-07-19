from pathlib import Path
import json

from musictagstudio.media_library.client import MusicBrainzClient


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(
            {
                "artists": [
                    {
                        "id": "abc",
                        "name": "Stieber Twins",
                    }
                ]
            }
        ).encode("utf-8")


def test_client_uses_cache(monkeypatch, tmp_path):
    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append(args)
        return Response()

    monkeypatch.setattr(
        "musictagstudio.media_library.client.urlopen",
        fake_urlopen,
    )

    client = MusicBrainzClient(
        cache_directory=tmp_path,
        cache_ttl_seconds=3600,
    )
    first, first_trace = client.get_json(
        "artist",
        {"query": "Stieber Twins"},
        result_key="artists",
    )
    second, second_trace = client.get_json(
        "artist",
        {"query": "Stieber Twins"},
        result_key="artists",
    )

    assert first == second
    assert len(calls) == 1
    assert first_trace.from_cache is False
    assert second_trace.from_cache is True


def test_client_uses_memory_cache_when_disk_write_fails(monkeypatch, tmp_path):
    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append(args)
        return Response()

    def fail_write(*args, **kwargs):
        raise OSError("temporarily locked")

    monkeypatch.setattr(
        "musictagstudio.media_library.client.urlopen",
        fake_urlopen,
    )
    monkeypatch.setattr(Path, "write_text", fail_write)

    client = MusicBrainzClient(
        cache_directory=tmp_path,
        cache_ttl_seconds=3600,
    )
    first, _ = client.get_json("artist", {"query": "Stieber Twins"})
    second, trace = client.get_json("artist", {"query": "Stieber Twins"})

    assert first == second
    assert len(calls) == 1
    assert trace.from_cache is True
