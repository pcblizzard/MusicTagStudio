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


def test_exact_live_suggestion_is_ranked_first(monkeypatch):
    from types import SimpleNamespace
    from musictagstudio.media_library import tasks

    controller = SimpleNamespace(
        suggest_artists=lambda *_args, **_kwargs: SimpleNamespace(
            artists=(SimpleNamespace(name="Clueso"),)
        )
    )
    monkeypatch.setattr(
        tasks,
        "suggest_deezer_artists",
        lambda *_args, **_kwargs: [SimpleNamespace(name="Die Fantastischen Vier")],
    )
    result = tasks._fetch_live_artist_suggestions(controller, "Clueso")
    assert [item.name for item in result] == [
        "Clueso", "Die Fantastischen Vier",
    ]
    assert not result[0].correction


def test_typo_uses_fuzzy_live_correction(monkeypatch):
    from types import SimpleNamespace
    from musictagstudio.media_library import tasks

    controller = SimpleNamespace(
        suggest_artists=lambda *_args, **_kwargs: SimpleNamespace(
            artists=(SimpleNamespace(name="Cleo"),)
        ),
        search_artists=lambda *_args, **_kwargs: SimpleNamespace(
            artists=(SimpleNamespace(name="Clueso"),)
        ),
    )
    monkeypatch.setattr(
        tasks, "suggest_deezer_artists",
        lambda *_args, **_kwargs: [SimpleNamespace(name="Claes")],
    )

    result = tasks._fetch_live_artist_suggestions(controller, "Clueos")

    assert result[0].name == "Clueso"
    assert result[0].correction is True


def test_typo_prefers_same_length_artist_over_literal_short_match(monkeypatch):
    from types import SimpleNamespace
    from musictagstudio.media_library import tasks

    captured = {}

    def search_artists(*_args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            artists=(
                SimpleNamespace(name="Clues"),
                SimpleNamespace(name="2 Clues"),
                SimpleNamespace(name="Clueso"),
            )
        )

    controller = SimpleNamespace(
        suggest_artists=lambda *_args, **_kwargs: SimpleNamespace(artists=()),
        search_artists=search_artists,
    )
    monkeypatch.setattr(tasks, "suggest_deezer_artists", lambda *_a, **_k: [])

    result = tasks._fetch_live_artist_suggestions(controller, "Cluoes")

    assert result[0] == tasks.LiveArtistSuggestion("Clueso", correction=True)
    assert captured["limit"] == 25
