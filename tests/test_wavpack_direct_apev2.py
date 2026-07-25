from mutagen.apev2 import APEv2

from musictagstudio.services import metadata_io


def test_wavpack_reader_does_not_require_wavpack_parser(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "high-rate.wv"
    path.write_bytes(b"dummy")

    tags = APEv2()
    tags["Title"] = "Stones in My Passway"
    tags["Artist"] = "Carmen Gomes Inc."
    tags["Track"] = "1/15"
    tags["Comment"] = (
        "DXD 32-352.8, Sound Liaison SL-1063A"
    )

    monkeypatch.setattr(
        metadata_io,
        "APEv2",
        lambda *args, **kwargs: tags,
    )

    song = metadata_io.read_metadata(path)

    assert song.title == "Stones in My Passway"
    assert song.artist == "Carmen Gomes Inc."
    assert song.track == "1"
    assert song.total_tracks == "15"
    assert "DXD" in song.comment
