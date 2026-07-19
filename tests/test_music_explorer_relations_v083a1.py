from pathlib import Path


def test_artist_relations_controller_and_ui_are_present():
    root = Path(__file__).parents[1]
    controller = (root / "src" / "musictagstudio" / "media_library" / "controller.py").read_text(encoding="utf-8")
    widget = (root / "src" / "musictagstudio" / "ui" / "media_library_widget.py").read_text(encoding="utf-8")

    assert "class ArtistRelation" in controller
    assert "def load_artist_relations" in controller
    assert '"artist-rels+label-rels"' in controller
    assert 'QLabel("Verknüpfungen")' in widget
    assert "def _relation_clicked" in widget
    assert "self.search_artist(relation.name)" in widget


def test_local_status_labels_are_user_friendly():
    root = Path(__file__).parents[1]
    widget = (root / "src" / "musictagstudio" / "ui" / "media_library_widget.py").read_text(encoding="utf-8")
    assert '"Lokal verfügbar"' in widget
    assert '"Externe Quelle nicht erreichbar"' in widget
    assert '"Nicht vorhanden"' in widget
