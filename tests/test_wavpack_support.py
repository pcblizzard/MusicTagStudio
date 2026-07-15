from musictagstudio.services.metadata_io import (
    SUPPORTED_AUDIO_EXTENSIONS,
    combine_number,
    split_number,
)


def test_wavpack_extension_is_supported():
    assert ".wv" in SUPPORTED_AUDIO_EXTENSIONS


def test_apev2_number_roundtrip():
    assert split_number("7/15") == (
        "7",
        "15",
    )
    assert combine_number(
        "7",
        "15",
    ) == "7/15"
