from io import BytesIO

from mutagen.apev2 import (
    APEBinaryValue,
    APEv2,
)
from PIL import Image

from musictagstudio.services import cover


def jpeg_bytes() -> bytes:
    output = BytesIO()

    with Image.new(
        "RGB",
        (600, 600),
    ) as image:
        image.save(
            output,
            format="JPEG",
        )

    return output.getvalue()


def test_wavpack_cover_is_read_directly_from_apev2(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "album.wv"
    path.write_bytes(b"dummy")
    data = jpeg_bytes()
    tags = APEv2()
    tags["Cover Art (Front)"] = APEBinaryValue(
        b"hello.jpg\x00"
        + data
    )

    monkeypatch.setattr(
        cover,
        "APEv2",
        lambda *args, **kwargs: tags,
    )

    info = cover.load_cover_info(
        path
    )

    assert info is not None
    assert info.data == data
    assert info.width == 600
    assert info.height == 600
    assert info.mime == "image/jpeg"


def test_wavpack_cover_key_is_case_insensitive(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "album.wv"
    path.write_bytes(b"dummy")
    data = jpeg_bytes()
    tags = APEv2()
    tags["COVER ART (FRONT)"] = APEBinaryValue(
        b"front.jpg\x00"
        + data
    )

    monkeypatch.setattr(
        cover,
        "APEv2",
        lambda *args, **kwargs: tags,
    )

    assert (
        cover.load_cover_info(
            path
        ).data
        == data
    )


def test_wavpack_cover_writer_uses_apev2(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "album.wv"
    path.write_bytes(b"dummy")
    tags = APEv2()
    saved = []

    monkeypatch.setattr(
        cover,
        "APEv2",
        lambda *args, **kwargs: tags,
    )
    monkeypatch.setattr(
        tags,
        "save",
        lambda target: saved.append(
            target
        ),
    )

    data = jpeg_bytes()
    cover.embed_cover(
        path,
        data,
    )

    raw = bytes(
        tags["Cover Art (Front)"]
    )

    assert raw.startswith(
        b"cover.jpg\x00"
    )
    assert raw.endswith(data)
    assert saved == [path]
