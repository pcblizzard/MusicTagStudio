from pathlib import Path

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from musictagstudio.settings import AppSettings, load_settings, save_settings
from musictagstudio.theme import apply_theme
from musictagstudio.ui.settings_dialog import SettingsDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_apple_light_preset_uses_red_accent():
    app = _app()
    apply_theme(app, "light", "apple")

    assert app.property("themeStyle") == "apple"
    assert (
        app.palette().color(QPalette.ColorRole.Highlight).name()
        == "#fa2d48"
    )
    assert "#f5f5f7" in app.styleSheet()
    assert "selection-background-color: #eeeef1" in app.styleSheet()
    assert "border-color: #d2d2d7" in app.styleSheet()


def test_apple_dark_preset_uses_graphite_background():
    app = _app()
    apply_theme(app, "dark", "apple")

    assert (
        app.palette().color(QPalette.ColorRole.Window).name()
        == "#1c1c1e"
    )
    assert "#fa2d55" in app.styleSheet()
    assert "background: #2c2c2e" in app.styleSheet()
    assert "border-right: 1px solid #3a3a3c" in app.styleSheet()


def test_unknown_preset_falls_back_to_standard():
    app = _app()
    apply_theme(app, "light", "unknown")

    assert app.property("themeStyle") == "standard"
    assert (
        app.palette().color(QPalette.ColorRole.Highlight).name()
        == "#2f80ed"
    )


def test_theme_style_roundtrip_and_invalid_fallback(tmp_path: Path):
    config = tmp_path / "config.toml"
    save_settings(
        AppSettings(theme="dark", theme_style="apple"),
        config,
    )
    assert load_settings(config).theme_style == "apple"

    config.write_text(
        '[appearance]\ntheme = "light"\nstyle = "unsupported"\n',
        encoding="utf-8",
    )
    assert load_settings(config).theme_style == "standard"


def test_settings_dialog_exposes_and_returns_theme_preset():
    _app()
    dialog = SettingsDialog(
        AppSettings(theme="dark", theme_style="apple"),
        embedded=True,
    )

    assert dialog.theme_combo.currentData() == "dark"
    assert dialog.theme_style_combo.currentData() == "apple"
    assert dialog.selected_settings().theme_style == "apple"
