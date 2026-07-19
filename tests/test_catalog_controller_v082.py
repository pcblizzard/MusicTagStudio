from musictagstudio.media_library.client import RequestTrace
from musictagstudio.media_library.controller import CatalogSearchController


class FakeClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.queries = []

    def get_json(self, endpoint, params, **kwargs):
        self.queries.append(params["query"])
        payload = self.payloads.pop(0)
        return payload, RequestTrace(
            url="https://example.invalid",
            status="200 OK",
            elapsed_ms=1,
            result_count=len(payload.get("artists", [])),
        )


def artist(name, score=100):
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "sort-name": name,
        "score": score,
    }


def test_exact_search_returns_immediately():
    client = FakeClient(
        [
            {
                "artists": [
                    artist("Stieber Twins")
                ]
            }
        ]
    )
    response = CatalogSearchController(
        client
    ).search_artists(
        "Stieber Twins"
    )

    assert len(client.queries) == 1
    assert response.exact_match is True
    assert response.suggestion_mode is False


def test_typo_reaches_fuzzy_stage():
    client = FakeClient(
        [
            {"artists": []},
            {"artists": []},
            {
                "artists": [
                    artist("Stieber Twins", 89)
                ]
            },
        ]
    )
    response = CatalogSearchController(
        client
    ).search_artists(
        "Steiber Twins"
    )

    assert len(client.queries) == 3
    assert "~0.75" in client.queries[-1]
    assert response.suggestion_mode is True
    assert response.artists[0].name == "Stieber Twins"


def test_broad_initial_results_do_not_prevent_typo_correction():
    client = FakeClient(
        [
            {
                "artists": [
                    artist("Twins"),
                    artist("Thompson Twins"),
                ]
            },
            {"artists": []},
            {
                "artists": [
                    artist("Stieber Twins", 89)
                ]
            },
        ]
    )

    response = CatalogSearchController(client).search_artists("Stiber Twins")

    assert len(client.queries) == 3
    assert response.suggestion_mode is True
    assert response.artists[0].name == "Stieber Twins"


def test_fuzzy_results_are_ranked_by_name_similarity():
    client = FakeClient(
        [
            {"artists": [artist("Berlin", 100)]},
            {"artists": []},
            {
                "artists": [
                    artist("Berlin", 100),
                    artist("Aggro Berlin", 80),
                ]
            },
        ]
    )

    response = CatalogSearchController(client).search_artists("Aggo Berlin")

    assert response.artists[0].name == "Aggro Berlin"
