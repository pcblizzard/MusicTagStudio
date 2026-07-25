from musictagstudio.provider_catalog import (
    PROVIDERS_BY_ID,
    supported_provider_ids,
)


def test_supported_providers():
    assert supported_provider_ids() == (
        "apple_music",
        "musicbrainz",
        "deezer",
    )


def test_qobuz_is_visible_but_not_selectable():
    qobuz = PROVIDERS_BY_ID["qobuz"]

    assert qobuz.status == "unsupported"
    assert not qobuz.selectable
