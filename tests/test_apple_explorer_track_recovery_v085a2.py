from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.providers import apple_music


def test_track_consensus_recovers_missing_album_search_result(monkeypatch) -> None:
    monkeypatch.setattr(apple_music, "search_album", lambda *_args, **_kwargs: [])

    def fake_song(title, *_args, **_kwargs):
        return [MetadataCandidate(
            source="apple_music", confidence=100, title=title,
            artist="Clueso", album_artist="Clueso", album="Deja Vu 1/2",
            year="2026", total_tracks="14", release_id="1859696286",
        )]

    monkeypatch.setattr(apple_music, "search_song", fake_song)
    result = apple_music.search_album_variants(
        "Deja Vu 1/2", "Clueso", expected_track_count=14,
        wanted_year="2026",
        track_titles=("Gib mir was Echtes", "Freier Fall", "Kissenmeer"),
    )
    assert result[0].collection_id == "1859696286"
    assert result[0].confidence >= apple_music.MINIMUM_ALBUM_CONFIDENCE
