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
    assert 'tr("file", self.language)' in main
    assert 'tr("add_folder", self.language)' in main
    assert 'tr("rescan", self.language)' in main
    assert '"home"' in main  # Navigation nutzt jetzt i18n-Keys statt Fixtext
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

    # Kennzahlen-Karten sind i18n-basiert (tr-Keys).
    for label in (
        '"albums"',
        '"artists"',
        '"indexed_tracks"',
        '"music_sources"',
    ):
        assert label in dashboard

    assert "def update_library" in dashboard
