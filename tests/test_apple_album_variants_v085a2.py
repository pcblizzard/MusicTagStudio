from musictagstudio.providers import apple_music
from musictagstudio.providers.apple_music import AppleAlbumCandidate


def test_album_search_retries_slash_title_without_slash(monkeypatch) -> None:
    queries = []

    def fake_search(album, artist, **kwargs):
        queries.append((album, artist))
        if album == "Deja Vu 1 2":
            return [
                AppleAlbumCandidate(
                    collection_id="1859696286",
                    album="Deja Vu 1/2",
                    artist="Clueso",
                    track_count=14,
                    year="2026",
                    country="DE",
                    confidence=100,
                )
            ]
        return []

    monkeypatch.setattr(apple_music, "search_album", fake_search)

    result = apple_music.search_album_variants(
        "Deja Vu 1/2",
        "Clueso",
        expected_track_count=14,
        wanted_year="2026",
    )

    assert queries[:2] == [
        ("Deja Vu 1/2", "Clueso"),
        ("Deja Vu 1 2", "Clueso"),
    ]
    assert result[0].collection_id == "1859696286"
