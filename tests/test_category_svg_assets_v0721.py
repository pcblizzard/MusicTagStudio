from pathlib import Path


def test_category_svg_assets_exist():
    directory = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "assets"
        / "icons"
    )

    for name in (
        "album.svg",
        "live.svg",
        "ep.svg",
        "single.svg",
        "compilation.svg",
        "other.svg",
    ):
        assert (
            directory
            / name
        ).is_file()
