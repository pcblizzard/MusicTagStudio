def test_settings_import_without_circular_dependency():
    from musictagstudio.settings import (
        AppSettings,
        load_settings,
    )

    assert AppSettings is not None
    assert callable(load_settings)


def test_media_library_import_after_settings():
    from musictagstudio.settings import (
        AppSettings,
    )
    from musictagstudio.media_library import (
        ReleaseGroup,
    )

    assert AppSettings is not None
    assert ReleaseGroup is not None
