from pathlib import Path


def source_text() -> str:
    path = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    )

    return path.read_text(
        encoding="utf-8"
    )


def test_comment_is_registered_in_optional_fields_and_table():
    text = source_text()

    assert (
        'OPTIONAL_FIELDS = ('
        in text
    )
    assert (
        '"comment",'
        in text
    )
    # Tabellen-Spaltenkopf ist jetzt i18n-basiert (tr("col_comment")).
    assert (
        'tr("col_comment"'
        in text
    )
    assert (
        "song.comment,"
        in text
    )


def test_optional_column_update_cannot_miss_comment():
    text = source_text()
    table_block = text.split(
        "self.table_fields = (",
        1,
    )[1].split(
        ")",
        1,
    )[0]

    assert '"comment"' in table_block
