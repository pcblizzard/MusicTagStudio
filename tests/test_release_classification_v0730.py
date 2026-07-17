from musictagstudio.media_library.discogs import (
    classify_release,
    release_badges,
)


def test_mixtape_title_beats_miscellaneous_type():
    assert (
        classify_release(
            title="Sternstunde M.I.X.T.A.P.E.",
            primary_type="Miscellaneous",
        )
        == "Mixtapes"
    )


def test_sampler_is_multi_artist_one_label():
    assert (
        classify_release(
            title="Aggro Ansage Nr. 3",
            artist_count=8,
            label_count=1,
        )
        == "Sampler"
    )


def test_compilation_is_multi_artist_multiple_labels():
    assert (
        classify_release(
            title="Bravo Hits",
            artist_count=40,
            label_count=4,
        )
        == "Compilations"
    )


def test_special_categories():
    assert (
        classify_release(
            title="Film Soundtrack",
        )
        == "Soundtracks"
    )
    assert (
        classify_release(
            title="Complete Albums Box Set",
        )
        == "Boxsets"
    )
    assert (
        classify_release(
            title="Live Bootleg",
        )
        == "Bootlegs"
    )


def test_badges_keep_physical_format_information():
    badges = release_badges(
        formats=("2×CD",),
        descriptions=(
            "Limited Edition",
            "Remastered",
        ),
        category="Sampler",
    )

    assert "Sampler" in badges
    assert "2×CD" in badges
    assert "Limited Edition" in badges
