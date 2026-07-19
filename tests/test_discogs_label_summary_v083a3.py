from musictagstudio.media_library.discogs import _release_from_label_summary


def test_label_summary_becomes_release_without_detail_request():
    release = _release_from_label_summary(
        {
            "id": 268464,
            "title": "Carlo, Cokxxx, Nutten",
            "year": 2003,
            "artist": "Sonny Black & Frank White",
            "format": "CD, Album, RP",
            "thumb": "https://example.invalid/cover.jpg",
            "resource_url": "https://api.discogs.com/releases/268464",
        },
        "Aggro Berlin",
    )

    assert release.release_id == 268464
    assert release.labels == ("Aggro Berlin",)
    assert release.formats == ("CD", "Album", "RP")
    assert release.artists == ("Sonny Black & Frank White",)
    assert release.cover_url == "https://example.invalid/cover.jpg"
