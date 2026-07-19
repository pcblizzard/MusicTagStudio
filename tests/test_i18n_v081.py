from musictagstudio.i18n import SUPPORTED_LANGUAGES, tr


def test_required_languages_are_available():
    codes = {code for code, _label in SUPPORTED_LANGUAGES}
    assert {"automatic", "de", "en", "es", "fr", "it", "pt_PT", "pt_BR"} <= codes


def test_save_button_is_localized():
    assert tr("save", "de") == "Speichern"
    assert tr("save", "en") == "Save"
    assert tr("save", "pt_BR") == "Salvar"


def test_core_german_menu_labels_are_available():
    assert tr("file", "de") == "Datei"
    assert tr("add_folder", "de") == "Ordner hinzufügen …"
    assert tr("settings", "de") == "Einstellungen …"
    assert tr("exit", "de") == "Beenden"
