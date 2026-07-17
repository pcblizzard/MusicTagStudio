from musictagstudio.models.song import Song


def test_song_model_has_comment_field():
    song = Song(
        comment="Testkommentar"
    )

    assert song.comment == "Testkommentar"
