from musictagstudio.normalizers import move_feature_artists


def test_square_brackets():
    title, artist = move_feature_artists(
        "Allein zu zweit [feat. DJ Mirko Machine]",
        "Stieber Twins",
    )

    assert title == "Allein zu zweit"
    assert artist == "Stieber Twins, DJ Mirko Machine"


def test_round_brackets():
    title, artist = move_feature_artists(
        "Allein zu zweit (feat. DJ Mirko Machine)",
        "Stieber Twins",
    )

    assert title == "Allein zu zweit"
    assert artist == "Stieber Twins, DJ Mirko Machine"


def test_plain_feature_at_end():
    title, artist = move_feature_artists(
        "Allein zu zweit feat. DJ Mirko Machine",
        "Stieber Twins",
    )

    assert title == "Allein zu zweit"
    assert artist == "Stieber Twins, DJ Mirko Machine"


def test_feature_and_version_are_preserved():
    title, artist = move_feature_artists(
        "Allein zu zweit (MagMar Remix) "
        "[feat. DJ Mirko Machine] [Instrumental]",
        "Stieber Twins",
    )

    assert title == "Allein zu zweit (MagMar Remix) [Instrumental]"
    assert artist == "Stieber Twins, DJ Mirko Machine"


def test_multiple_feature_artists_and_duplicates():
    title, artist = move_feature_artists(
        "Titel [feat. Artist A & Artist B]",
        "Main Artist, Artist A",
    )

    assert title == "Titel"
    assert artist == "Main Artist, Artist A, Artist B"
