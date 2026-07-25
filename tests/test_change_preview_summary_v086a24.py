from musictagstudio.ui.change_preview_dialog import _summary_text


def _changes(n: int, subject: str = "Titel") -> list[tuple[str, str, str, str]]:
    return [(subject, f"Feld{i}", "a", "b") for i in range(n)]


def test_summary_names_field_changes_and_affected_titles():
    text = _summary_text(_changes(56), file_count=9)
    assert text == "56 Änderungen an 9 Titeln werden geschrieben."


def test_summary_singular_grammar():
    text = _summary_text(_changes(1), file_count=1)
    assert text == "1 Änderung an 1 Titel wird geschrieben."


def test_summary_falls_back_to_distinct_subjects():
    changes = _changes(2, "A") + _changes(3, "B")
    text = _summary_text(changes, file_count=None)
    assert text == "5 Änderungen an 2 Titeln werden geschrieben."
