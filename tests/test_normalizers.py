from musictagstudio.core.normalizers import (
    move_feature_artists,
    normalize_genre,
    normalize_text,
)


def test_feature_variants():
    for title in (
        "Song [feat. Guest]",
        "Song (feat. Guest)",
        "Song feat. Guest",
        "Song [ft Guest]",
    ):
        cleaned, artist = move_feature_artists(title, "Main")
        assert cleaned == "Song"
        assert artist == "Main, Guest"


def test_feature_keeps_versions():
    cleaned, artist = move_feature_artists(
        "Song (Remix) [feat. Guest] [Instrumental]",
        "Main",
    )
    assert cleaned == "Song (Remix) [Instrumental]"
    assert artist == "Main, Guest"


def test_apostrophe_and_genre():
    assert normalize_text("Chris’ Interlude") == "Chris' Interlude"
    assert normalize_genre("Hip Hop/Rap") == "Hip-Hop, Rap"
