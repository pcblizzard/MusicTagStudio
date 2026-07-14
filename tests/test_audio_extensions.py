from musictagstudio.services.metadata_io import SUPPORTED_AUDIO_EXTENSIONS

def test_common_audio_extensions_supported():
    assert {'.flac','.mp3','.ogg','.opus','.m4a'} <= SUPPORTED_AUDIO_EXTENSIONS
