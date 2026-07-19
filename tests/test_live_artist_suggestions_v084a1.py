from musictagstudio.media_library.controller import CatalogSearchController


class Client:
    def __init__(self):
        self.params = None

    def get_json(self, endpoint, params, *, result_key):
        self.params = params
        return (
            {
                "artists": [
                    {"id": "1", "name": "Mark Forster", "score": 100},
                    {"id": "2", "name": "Bruno Mars", "score": 95},
                ]
            },
            object(),
        )


def test_live_suggestions_use_one_prefix_query():
    client = Client()
    result = CatalogSearchController(client).suggest_artists("Mar")

    assert [artist.name for artist in result.artists] == [
        "Mark Forster",
        "Bruno Mars",
    ]
    assert client.params["query"] == "artist:Mar* OR artist:Mar"


def test_live_suggestions_ignore_queries_shorter_than_three_characters():
    client = Client()

    result = CatalogSearchController(client).suggest_artists("Ma")

    assert result.artists == ()
    assert client.params is None


def test_media_library_has_debounced_suggestion_panel():
    from pathlib import Path

    source = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "media_library_widget.py"
    ).read_text(encoding="utf-8")

    assert "self._suggestion_timer.setInterval(450)" in source
    assert "_fetch_live_artist_suggestions" in source
    assert 'setObjectName("liveSearchSuggestions")' in source
