from mutagen.apev2 import APEv2

from musictagstudio.models.song import Song
from musictagstudio.services.metadata_io import (
    _read_apev2,
    _write_apev2,
)


class FakeWavPack:
    def __init__(self):
        self.tags = APEv2()


def test_wavpack_apev2_read_and_write(
    tmp_path,
):
    audio = FakeWavPack()
    song = Song(
        title="Minimum",
        artist="Clueso",
        album_artist="Clueso",
        album="Deja Vu 1/2",
        genre="Pop",
        year="2026",
        track="7",
        total_tracks="14",
        disc="1",
        total_discs="1",
        isrc="DETEST123456",
        label="Example",
        copyright="© Example",
        composer="Composer",
        comment="DXD 32-352.8",
    )

    _write_apev2(
        audio.tags,
        song,
    )
    loaded = _read_apev2(
        tmp_path / "test.wv",
        audio,
    )

    assert loaded.title == "Minimum"
    assert loaded.artist == "Clueso"
    assert loaded.album_artist == "Clueso"
    assert loaded.track == "7"
    assert loaded.total_tracks == "14"
    assert loaded.comment == (
        "DXD 32-352.8"
    )
