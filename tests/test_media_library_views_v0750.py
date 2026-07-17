from pathlib import Path

def test_views_exist():
    text=(Path(__file__).parents[1]/"src/musictagstudio/ui/media_library_widget.py").read_text(encoding="utf-8")
    for value in ("Discografie","Tabelle","Coverraster","Cover + Liste"): assert value in text
    assert "QStackedWidget" in text
    assert '"media_library/view_mode"' in text
    assert '"media_library/cover_size"' in text
