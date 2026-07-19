from musictagstudio.media_library import service


def artist(name: str, score: int = 100):
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "sort-name": name,
        "score": score,
    }


def test_exact_artist_search_uses_one_request(monkeypatch):
    calls = []

    def fake_request(url):
        calls.append(url)
        return {
            "artists": [
                artist("Stieber Twins")
            ]
        }

    monkeypatch.setattr(
        service,
        "_request_json",
        fake_request,
    )
    result = service.search_artists_with_fallback(
        "Stieber Twins"
    )

    assert len(calls) == 1
    assert result.used_fuzzy_search is False
    assert result.artists[0].name == "Stieber Twins"


def test_typo_uses_fuzzy_search_and_returns_suggestion(monkeypatch):
    calls = []

    def fake_request(url):
        calls.append(url)
        if len(calls) == 1:
            return {"artists": []}
        return {
            "artists": [
                artist("Stieber Twins", 92)
            ]
        }

    monkeypatch.setattr(
        service,
        "_request_json",
        fake_request,
    )
    result = service.search_artists_with_fallback(
        "Steiber Twins"
    )

    assert len(calls) == 2
    assert "~0.8" in calls[1]
    assert result.used_fuzzy_search is True
    assert result.artists[0].name == "Stieber Twins"
