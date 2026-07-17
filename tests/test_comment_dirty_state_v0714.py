from musictagstudio.core.merger import (
    song_values,
)
from musictagstudio.models.metadata import (
    EDITABLE_FIELDS,
    FIELD_LABELS,
)
from musictagstudio.models.song import Song


def test_comment_is_part_of_editable_fields():
    assert "comment" in EDITABLE_FIELDS
    assert FIELD_LABELS["comment"] == "Kommentar"


def test_loaded_comment_is_part_of_original_values():
    song = Song(
        title="Titel",
        comment="Vorhandener Kommentar",
    )

    values = song_values(song)

    assert values["comment"] == "Vorhandener Kommentar"


def test_unchanged_editor_values_are_not_dirty():
    song = Song(
        title="Titel",
        artist="Interpret",
        comment="Kommentar",
    )
    original_values = song_values(song)
    current_values = dict(original_values)

    assert current_values == original_values
