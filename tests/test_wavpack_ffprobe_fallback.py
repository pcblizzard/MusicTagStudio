
from musictagstudio.services import metadata_io


def test_wavpack_uses_ffprobe_when_both_mutagen_readers_fail(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "dxd.wv"
    path.write_bytes(b"dummy")

    def fail(*args, **kwargs):
        raise IndexError(
            "list index out of range"
        )

    monkeypatch.setattr(
        metadata_io,
        "APEv2",
        fail,
    )
    monkeypatch.setattr(
        metadata_io,
        "WavPack",
        fail,
    )
    monkeypatch.setattr(
        metadata_io,
        "_read_ffprobe_tags",
        lambda value: {
            "title": "Passway Opening Credits",
            "artist": "Carmen Gomes Inc.",
            "album": "Stones in My Passway",
            "album artist": "Carmen Gomes Inc.",
            "track": "1/15",
            "year": "2023",
            "genre": "Jazz",
            "comment": (
                "DXD 32-352.8, Sound Liaison SL-1063A"
            ),
        },
    )

    song = metadata_io.read_metadata(
        path
    )

    assert song.title == (
        "Passway Opening Credits"
    )
    assert song.artist == (
        "Carmen Gomes Inc."
    )
    assert song.track == "1"
    assert song.total_tracks == "15"
    assert song.year == "2023"
    assert "DXD" in song.comment


def test_ffprobe_tag_keys_are_case_insensitive(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "case.wv"
    path.write_bytes(b"dummy")

    monkeypatch.setattr(
        metadata_io,
        "APEv2",
        lambda *args, **kwargs:
        (_ for _ in ()).throw(
            ValueError("no ape")
        ),
    )
    monkeypatch.setattr(
        metadata_io,
        "WavPack",
        lambda *args, **kwargs:
        (_ for _ in ()).throw(
            ValueError("no wavpack")
        ),
    )
    monkeypatch.setattr(
        metadata_io,
        "_read_ffprobe_tags",
        lambda value: {
            "title": "Title",
            "albumartist": "Album Artist",
            "tracknumber": "7/15",
        },
    )

    song = metadata_io.read_metadata(
        path
    )

    assert song.album_artist == (
        "Album Artist"
    )
    assert song.track == "7"
    assert song.total_tracks == "15"
