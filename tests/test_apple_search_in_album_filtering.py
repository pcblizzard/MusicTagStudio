from musictagstudio.providers import apple_music


def test_strict_album_search_rejects_wrong_track(
    monkeypatch,
):
    payload = {
        "results": [
            {
                "wrapperType": "track",
                "kind": "song",
                "collectionId": 1859696286,
                "trackId": 1859696302,
                "trackNumber": 11,
                "discNumber": 1,
                "trackName": "Jedes Jahr",
                "artistName": "Clueso",
                "collectionArtistName": "Clueso",
                "collectionName": "Deja Vu 1/2",
                "trackCount": 14,
                "discCount": 1,
                "releaseDate": (
                    "2026-02-27T12:00:00Z"
                ),
            },
            {
                "wrapperType": "track",
                "kind": "song",
                "collectionId": 1859696286,
                "trackId": 1859696298,
                "trackNumber": 7,
                "discNumber": 1,
                "trackName": "Minimum",
                "artistName": "Clueso",
                "collectionArtistName": "Clueso",
                "collectionName": "Deja Vu 1/2",
                "trackCount": 14,
                "discCount": 1,
                "releaseDate": (
                    "2026-02-27T12:00:00Z"
                ),
            },
        ]
    }

    monkeypatch.setattr(
        apple_music,
        "_search_payload",
        lambda *args, **kwargs: payload,
    )

    results = (
        apple_music.search_song_in_album(
            "Minimum",
            "Clueso",
            "Deja Vu 1/2",
            collection_id=(
                "1859696286"
            ),
            wanted_track="07",
            wanted_disc="1",
            countries=("DE", "US"),
        )
    )

    assert len(results) == 1
    assert results[0].title == "Minimum"
    assert results[0].track == "7"
    assert (
        results[0].external_id
        == "1859696298"
    )
