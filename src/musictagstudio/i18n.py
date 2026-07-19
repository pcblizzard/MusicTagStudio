from __future__ import annotations

import locale
from typing import Final


SUPPORTED_LANGUAGES: Final[tuple[tuple[str, str], ...]] = (
    ("automatic", "Automatisch (System)"),
    ("de", "Deutsch"),
    ("en", "English"),
    ("es", "Español"),
    ("fr", "Français"),
    ("it", "Italiano"),
    ("pt_PT", "Português (Portugal)"),
    ("pt_BR", "Português (Brasil)"),
)

_TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "de": {
        "automatic_system": "Automatisch (System)",
        "file": "Datei",
        "edit": "Bearbeiten",
        "add_folder": "Ordner hinzufügen …",
        "rescan": "Neu einlesen",
        "settings": "Einstellungen …",
        "exit": "Beenden",
        "undo": "Rückgängig",
        "redo": "Wiederholen",
        "history": "Änderungsverlauf",
        "reset_columns": "Spaltenbreiten zurücksetzen",
        "home": "Startseite",
        "tagger": "Tagger",
        "media_library": "Medienbibliothek",
        "audio_analysis": "Audio-Analyse",
        "library_audit": "Bibliotheksprüfung",
        "ready": "Bereit",
        "save": "Speichern",
        "cancel": "Abbrechen",
        "language": "Sprache:",
        "appearance": "Darstellung",
        "theme": "Theme:",
        "theme_auto": "Automatisch (Windows-Einstellung)",
        "theme_light": "Hell",
        "theme_dark": "Dunkel",
        "welcome": "Willkommen bei MusicTagStudio",
        "dashboard_subtitle": "Bibliothek verwalten, Metadaten bearbeiten und die Sammlung prüfen.",
        "albums": "Alben",
        "artists": "Künstler",
        "indexed_tracks": "Indizierte Titel",
        "music_sources": "Musikquellen",
        "source_status": "Quellenstatus",
        "no_source": "Noch keine aktive Musikquelle eingerichtet.",
        "add_music_source": "Musikquelle hinzufügen …",
        "refresh_library": "Bibliotheksdaten aktualisieren",
        "search_artist_placeholder": "Künstler suchen, z. B. Stieber Twins",
        "search": "Suchen",
        "search_results": "Suchtreffer",
        "releases": "Veröffentlichungen",
        "view": "Ansicht:",
        "cover_size": "Covergröße:",
        "search_running": "Suche läuft …",
        "artist_search": "Künstlersuche nach „{query}“ …",
        "artists_found": "{count} Künstler gefunden.",
        "suggestion": "Vorschlag …",
        "batch_suggestion": "Mehrfachvorschlag …",
        "cover": "Cover …",
        "link_or_id": "Link oder ID …",
        "bbcode": "BBCode-Text …",
        "more_artist": "Mehr vom Künstler",
        "music_folder": "Musikordner auswählen",
        "library_rescan": "Bibliothek neu einlesen",
    },
    "en": {
        "automatic_system": "Automatic (System)",
        "file": "File",
        "edit": "Edit",
        "add_folder": "Add folder…",
        "rescan": "Rescan",
        "settings": "Settings…",
        "exit": "Exit",
        "undo": "Undo",
        "redo": "Redo",
        "history": "Change history",
        "reset_columns": "Reset column widths",
        "home": "Home",
        "tagger": "Tagger",
        "media_library": "Media library",
        "audio_analysis": "Audio analysis",
        "library_audit": "Library audit",
        "ready": "Ready",
        "save": "Save",
        "cancel": "Cancel",
        "language": "Language:",
        "appearance": "Appearance",
        "theme": "Theme:",
        "theme_auto": "Automatic (Windows setting)",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "welcome": "Welcome to MusicTagStudio",
        "dashboard_subtitle": "Manage your library, edit metadata and check your collection.",
        "albums": "Albums",
        "artists": "Artists",
        "indexed_tracks": "Indexed tracks",
        "music_sources": "Music sources",
        "source_status": "Source status",
        "no_source": "No active music source has been configured.",
        "add_music_source": "Add music source…",
        "refresh_library": "Refresh library data",
        "search_artist_placeholder": "Search artists, e.g. Stieber Twins",
        "search": "Search",
        "search_results": "Search results",
        "releases": "Releases",
        "view": "View:",
        "cover_size": "Cover size:",
        "search_running": "Searching…",
        "artist_search": "Searching for artist “{query}”…",
        "artists_found": "{count} artists found.",
        "suggestion": "Suggestion…",
        "batch_suggestion": "Batch suggestion…",
        "cover": "Cover…",
        "link_or_id": "Link or ID…",
        "bbcode": "BBCode text…",
        "more_artist": "More by artist",
        "music_folder": "Choose music folder",
        "library_rescan": "Rescan library",
    },
    "es": {
        "automatic_system": "Automático (Sistema)",
        "file": "Archivo", "edit": "Editar", "add_folder": "Añadir carpeta…",
        "rescan": "Volver a analizar", "settings": "Configuración…", "exit": "Salir",
        "undo": "Deshacer", "redo": "Rehacer", "home": "Inicio", "tagger": "Etiquetador",
        "media_library": "Biblioteca multimedia", "audio_analysis": "Análisis de audio",
        "library_audit": "Comprobación de biblioteca", "ready": "Listo",
        "save": "Guardar", "cancel": "Cancelar", "language": "Idioma:",
        "appearance": "Apariencia", "theme": "Tema:", "theme_auto": "Automático (configuración de Windows)",
        "theme_light": "Claro", "theme_dark": "Oscuro", "search": "Buscar",
    },
    "fr": {
        "automatic_system": "Automatique (Système)",
        "file": "Fichier", "edit": "Édition", "add_folder": "Ajouter un dossier…",
        "rescan": "Réanalyser", "settings": "Paramètres…", "exit": "Quitter",
        "undo": "Annuler", "redo": "Rétablir", "home": "Accueil", "tagger": "Éditeur de tags",
        "media_library": "Médiathèque", "audio_analysis": "Analyse audio",
        "library_audit": "Vérification de la bibliothèque", "ready": "Prêt",
        "save": "Enregistrer", "cancel": "Annuler", "language": "Langue:",
        "appearance": "Apparence", "theme": "Thème:", "theme_auto": "Automatique (paramètre Windows)",
        "theme_light": "Clair", "theme_dark": "Sombre", "search": "Rechercher",
    },
    "it": {
        "automatic_system": "Automatico (Sistema)",
        "file": "File", "edit": "Modifica", "add_folder": "Aggiungi cartella…",
        "rescan": "Rileggi", "settings": "Impostazioni…", "exit": "Esci",
        "undo": "Annulla", "redo": "Ripeti", "home": "Home", "tagger": "Editor tag",
        "media_library": "Libreria multimediale", "audio_analysis": "Analisi audio",
        "library_audit": "Controllo libreria", "ready": "Pronto",
        "save": "Salva", "cancel": "Annulla", "language": "Lingua:",
        "appearance": "Aspetto", "theme": "Tema:", "theme_auto": "Automatico (impostazione Windows)",
        "theme_light": "Chiaro", "theme_dark": "Scuro", "search": "Cerca",
    },
    "pt_PT": {
        "automatic_system": "Automático (Sistema)",
        "file": "Ficheiro", "edit": "Editar", "add_folder": "Adicionar pasta…",
        "rescan": "Voltar a analisar", "settings": "Definições…", "exit": "Sair",
        "undo": "Anular", "redo": "Refazer", "home": "Início", "tagger": "Editor de etiquetas",
        "media_library": "Biblioteca multimédia", "audio_analysis": "Análise de áudio",
        "library_audit": "Verificação da biblioteca", "ready": "Pronto",
        "save": "Guardar", "cancel": "Cancelar", "language": "Idioma:",
        "appearance": "Aspeto", "theme": "Tema:", "theme_auto": "Automático (definição do Windows)",
        "theme_light": "Claro", "theme_dark": "Escuro", "search": "Pesquisar",
    },
    "pt_BR": {
        "automatic_system": "Automático (Sistema)",
        "file": "Arquivo", "edit": "Editar", "add_folder": "Adicionar pasta…",
        "rescan": "Verificar novamente", "settings": "Configurações…", "exit": "Sair",
        "undo": "Desfazer", "redo": "Refazer", "home": "Início", "tagger": "Editor de tags",
        "media_library": "Biblioteca de mídia", "audio_analysis": "Análise de áudio",
        "library_audit": "Verificação da biblioteca", "ready": "Pronto",
        "save": "Salvar", "cancel": "Cancelar", "language": "Idioma:",
        "appearance": "Aparência", "theme": "Tema:", "theme_auto": "Automático (configuração do Windows)",
        "theme_light": "Claro", "theme_dark": "Escuro", "search": "Pesquisar",
    },
}


def system_language() -> str:
    value = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "en").replace("-", "_")
    if value.lower().startswith("pt_br"):
        return "pt_BR"
    if value.lower().startswith("pt"):
        return "pt_PT"
    prefix = value.split("_", 1)[0].lower()
    return prefix if prefix in {"de", "en", "es", "fr", "it"} else "en"


def resolve_language(value: str) -> str:
    return system_language() if value == "automatic" else value if value in _TRANSLATIONS else "en"


def tr(key: str, language: str = "automatic", **values) -> str:
    resolved = resolve_language(language)
    text = _TRANSLATIONS.get(resolved, {}).get(key)
    if text is None:
        text = _TRANSLATIONS["en"].get(key, key)
    return text.format(**values) if values else text
