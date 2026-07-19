import json

from musictagstudio.media_library import discogs


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"results": []}).encode("utf-8")


def test_personal_token_uses_authorization_header(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(discogs.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(discogs, "REQUEST_INTERVAL_SECONDS", 0)

    discogs._get_json("/database/search", "secret", {"q": "Sido"})

    request = captured["request"]
    assert request.get_header("Authorization") == "Discogs token=secret"
    assert "secret" not in request.full_url
    assert captured["timeout"] == 20
