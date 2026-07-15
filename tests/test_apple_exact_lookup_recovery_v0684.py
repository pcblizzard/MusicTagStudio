from musictagstudio import direct_album_lookup
from musictagstudio.direct_album_lookup import (
    DirectAlbumResult,
    DirectAlbumTrack,
    find_apple_track_in_album,
)


def make_track(
    number: int,
    title: str,
    external_id: str,
) -> DirectAlbumTrack:
    return DirectAlbumTrack(
        title=title,
        artist="Clueso",
        album_artist="Clueso",
        album="Deja Vu 1/2",
        genre="Pop",
        year="2026",
        track=str(number),
        total_tracks="14",
        disc="1",
        total_discs="1",
        external_id=external_id,
    )


def test_exact_lookup_falls_back_to_us_store(
    monkeypatch,
):
    calls = []

    def fake_lookup(
        collection_id,
        *,
        country,
    ):
        calls.append(country)

        if country == "DE":
            tracks = (
                make_track(
                    11,
                    "Jedes Jahr",
                    "1859696302",
                ),
            )
        else:
            tracks = (
                make_track(
                    7,
                    "Minimum",
                    "1859696298",
                ),
            )

        return DirectAlbumResult(
            provider="apple_music",
            album="Deja Vu 1/2",
            album_artist="Clueso",
            tracks=tracks,
        )

    monkeypatch.setattr(
        direct_album_lookup,
        "lookup_apple_album_by_id",
        fake_lookup,
    )

    result = find_apple_track_in_album(
        "1859696286",
        7,
        1,
        countries=("DE", "US"),
    )

    assert result is not None
    assert result.title == "Minimum"
    assert result.external_id == "1859696298"
    assert calls == ["DE", "US"]


def test_exact_lookup_rejects_wrong_track(
    monkeypatch,
):
    monkeypatch.setattr(
        direct_album_lookup,
        "lookup_apple_album_by_id",
        lambda *args, **kwargs:
        DirectAlbumResult(
            provider="apple_music",
            album="Deja Vu 1/2",
            album_artist="Clueso",
            tracks=(
                make_track(
                    11,
                    "Jedes Jahr",
                    "1859696302",
                ),
            ),
        ),
    )

    assert find_apple_track_in_album(
        "1859696286",
        7,
        1,
        countries=("DE", "US"),
    ) is None
