import io
import json

from musictagstudio.providers.deezer import suggest_artists


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def test_deezer_artist_suggestions_prioritize_popular_matches(monkeypatch):
    payload = {
        "data": [
            {"name": "MAR!", "nb_fan": 3},
            {"name": "Bruno Mars", "nb_fan": 12_000_000},
            {"name": "Mark Forster", "nb_fan": 500_000},
        ]
    }
    monkeypatch.setattr(
        "musictagstudio.providers.deezer.urlopen",
        lambda *_args, **_kwargs: Response(json.dumps(payload).encode()),
    )

    suggestions = suggest_artists("Mar")

    assert [item.name for item in suggestions] == [
        "Bruno Mars",
        "Mark Forster",
        "MAR!",
    ]
