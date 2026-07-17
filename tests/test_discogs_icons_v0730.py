from pathlib import Path


def test_new_svg_icons_exist():
    directory = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "assets"
        / "icons"
    )

    for name in (
        "mixtape.svg",
        "sampler.svg",
        "soundtrack.svg",
        "boxset.svg",
        "bootleg.svg",
    ):
        assert (
            directory
            / name
        ).is_file()
