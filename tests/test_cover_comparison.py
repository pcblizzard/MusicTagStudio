from musictagstudio.services.cover import (
    CoverInfo,
    covers_are_identical,
)


def make_cover(
    md5: str = "abc",
    width: int = 1000,
    height: int = 1000,
    mime: str = "image/jpeg",
) -> CoverInfo:
    return CoverInfo(
        data=b"cover",
        mime=mime,
        width=width,
        height=height,
        depth=24,
        colors=0,
        picture_type=3,
        md5=md5,
    )


def test_identical_cover_signatures():
    assert covers_are_identical(
        [
            make_cover(),
            make_cover(),
            make_cover(),
        ]
    )


def test_different_md5_is_not_identical():
    assert not covers_are_identical(
        [
            make_cover(md5="abc"),
            make_cover(md5="def"),
        ]
    )


def test_different_dimensions_are_not_identical():
    assert not covers_are_identical(
        [
            make_cover(width=1000),
            make_cover(width=1200),
        ]
    )


def test_all_missing_covers_are_identical():
    assert covers_are_identical(
        [None, None, None]
    )


def test_mixed_missing_and_present_is_not_identical():
    assert not covers_are_identical(
        [make_cover(), None]
    )
