from pathlib import Path


def test_dashboard_workspace_and_toolbar_exist():
    main = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "main_window.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "DashboardWidget" in main
    assert "def create_toolbar" not in main
    assert '"Datei"' in main
    assert '"Ordner hinzufügen …"' in main
    assert '"Neu einlesen"' in main
    assert '"Startseite"' in main
    assert "self.statusBar().showMessage" in main


def test_dashboard_has_library_metrics():
    dashboard = (
        Path(__file__).parents[1]
        / "src"
        / "musictagstudio"
        / "ui"
        / "dashboard_widget.py"
    ).read_text(
        encoding="utf-8"
    )

    for label in (
        '"Alben"',
        '"Künstler"',
        '"Indizierte Titel"',
        '"Musikquellen"',
    ):
        assert label in dashboard

    assert "def update_library" in dashboard
