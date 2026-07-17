import json

from musictagstudio import direct_album_lookup


def apple_payload():
    return {
        "resultCount": 4,
        "results": [
            {
                "wrapperType": "collection",
                "collectionId": 1859696286,
                "collectionName": "Deja Vu 1/2",
                "artistName": "Clueso",
                "trackCount": 14,
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
                "trackCount": 14,
                "discCount": 1,
            },
            {
                "wrapperType": "track",
                "kind": None,
                "collectionId": 1859696286,
                "trackId": 999,
                "trackNumber": 8,
                "discNumber": 1,
                "trackName": "Rejected",
            },
            {
                "wrapperType": "track",
                "kind": "song",
                "collectionId": 999,
                "trackId": 1000,
                "trackNumber": 9,
                "discNumber": 1,
                "trackName": "Wrong collection",
            },
        ],
    }


def test_lookup_writes_raw_json_and_keeps_valid_track(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        direct_album_lookup,
        "_get_json",
        lambda url: apple_payload(),
    )

    result = (
        direct_album_lookup
        .lookup_apple_album_by_id(
            "1859696286",
            country="US",
        )
    )

    assert len(result.tracks) == 1
    assert result.tracks[0].title == "Minimum"

    dump = (
        tmp_path
        / "cache"
        / "apple"
        / "lookup_1859696286_US.json"
    )
    assert dump.exists()
    payload = json.loads(
        dump.read_text(
            encoding="utf-8"
        )
    )
    assert (
        payload["results"][1][
            "trackName"
        ]
        == "Minimum"
    )


def test_rejection_reasons_are_explicit():
    reasons = (
        direct_album_lookup
        ._apple_track_rejection_reasons(
            {
                "wrapperType": "track",
                "kind": None,
                "collectionId": 999,
                "trackName": "",
            },
            "1859696286",
        )
    )

    assert any(
        "kind" in reason
        for reason in reasons
    )
    assert (
        "collectionId stimmt nicht"
        in reasons
    )
    assert "trackNumber fehlt" in reasons
    assert "discNumber fehlt" in reasons
    assert "trackId fehlt" in reasons
    assert "trackName fehlt" in reasons
