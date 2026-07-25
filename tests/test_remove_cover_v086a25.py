from io import BytesIO

from PIL import Image

from musictagstudio.models.song import Song
from musictagstudio.services import cover
from musictagstudio.services.metadata_io import save_song_metadata


def _jpeg() -> bytes:
    output = BytesIO()
    with Image.new("RGB", (400, 400)) as image:
        image.save(output, format="JPEG")
    return output.getvalue()


def _wavpack_with_tags(tmp_path):
    # Eine echte, getaggte WavPack-Datei (APEv2 hängt am Dateiende, ein
    # gültiger Audiostream ist dafür nicht nötig).
    path = tmp_path / "album.wv"
    path.write_bytes(b"dummy")
    save_song_metadata(str(path), Song(title="Titel", artist="Kuenstler"))
    return str(path)


def test_remove_cover_wavpack_roundtrip(tmp_path):
    path = _wavpack_with_tags(tmp_path)

    cover.embed_cover(path, _jpeg())
    assert cover.load_cover(path) is not None

    cover.remove_cover(path)
    assert cover.load_cover(path) is None


def test_remove_cover_without_existing_cover_is_safe(tmp_path):
    path = _wavpack_with_tags(tmp_path)
    # Kein Cover vorhanden -> darf nicht scheitern.
    cover.remove_cover(path)
    assert cover.load_cover(path) is None
