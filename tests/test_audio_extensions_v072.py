from musictagstudio.services.metadata_io import (
    SUPPORTED_AUDIO_EXTENSIONS,
)


def test_new_audio_extensions_are_registered():
    assert ".ape" in SUPPORTED_AUDIO_EXTENSIONS
    assert ".wma" in SUPPORTED_AUDIO_EXTENSIONS
    assert ".asf" in SUPPORTED_AUDIO_EXTENSIONS
    assert ".m4b" in SUPPORTED_AUDIO_EXTENSIONS
