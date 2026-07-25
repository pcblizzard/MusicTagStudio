# Architektur von MusicTagStudio

MusicTagStudio verwendet eine schichtweise Paketstruktur. Neue Funktionen
sollen in das fachlich passende Paket eingeordnet werden; zusätzliche große
Module direkt unter `musictagstudio` sind zu vermeiden.

## Einstiegspunkt

`musictagstudio.main` startet die Anwendung und erzeugt
`ui.main_window.MainWindow`. Es gibt genau eine produktive MainWindow-Klasse.

## Pakete und Verantwortungen

- `ui/`: Qt-Widgets, Dialoge, Navigation und Darstellung. Netzwerkzugriffe und
  Datenumwandlungen werden an Fachmodule delegiert.
- `models/`: gemeinsam verwendete, von der Oberfläche unabhängige Datenmodelle.
- `core/`: allgemeine Regeln zum Vergleichen, Normalisieren und Zusammenführen.
- `services/`: Anwendungsfälle für Tagging, Scannen, Cover und Vorschläge.
- `providers/`: Adapter zu externen Diensten wie Apple Music, Deezer und
  LRCLIB. Provider dürfen keine Qt-Abhängigkeit besitzen.
- `media_library/`: MusicBrainz-/Discogs-Suche und Explorer-Fachlogik.
  `tasks.py` enthält langsame Netzwerk- und Cache-Aufgaben;
  `presentation.py` enthält reine Formatierungs- und Zusammenführungslogik.
  `streaming/` enthält anbieterneutrale Modelle, die parallele Koordination
  von Apple Music, TIDAL und Spotify sowie den SQLite-Cache für externe IDs.
  Die TIDAL-Benutzeranmeldung verwendet OAuth 2.0 Authorization Code mit
  PKCE; Access- und Refresh-Token liegen ausschließlich im
  Betriebssystem-Tresor
  und zeitlich begrenzte Verfügbarkeitsprüfungen.
- `lyrics/`: Lyrics-Modelle, lokale Speicherung, LRC-Verarbeitung und Auswahl.
- `audio_analysis/`, `library_audit/`, `cover_management/`: eigenständige
  Funktionsbereiche mit ihren jeweiligen Modellen und Abläufen.

## Abhängigkeitsrichtung

Die Oberfläche darf Fachmodule verwenden. Fachmodule dürfen weder Widgets
importieren noch UI-Zustand verändern. Provider liefern Daten oder klar
definierte Fehler zurück; Dialoge entscheiden über die Darstellung.

```text
ui -> services / media_library / lyrics -> providers / core / models
```

Zyklische Imports werden nicht durch verzögerte UI-Imports kaschiert, sondern
durch das Verschieben gemeinsam benötigter Modelle oder Funktionen aufgelöst.

## Kompatibilitätsmodule

Die kleinen Root-Module `editor.py`, `metadata.py`, `scanner.py`, `song.py`,
`cover.py` und `normalizers.py` bleiben vorerst als öffentliche Importbrücken
bestehen. Neue interne Aufrufe verwenden immer das eigentliche Zielpaket. Eine
Entfernung dieser Brücken ist nur in einer angekündigten inkompatiblen Version
vorgesehen.

## Größen- und Aufteilungsregeln

- Qt-Klassen koordinieren; reine Berechnung und I/O liegen außerhalb der UI.
- Ab etwa 800 bis 1.000 Zeilen wird geprüft, ob mehrere Verantwortungen in
  einem Modul stecken. Die Zeilenzahl allein ist kein Grund für eine Trennung.
- Ein allgemeines `utils`-Sammelpaket wird vermieden. Hilfsfunktionen erhalten
  einen fachlichen Ort und Namen.
- Refactorings bewahren bestehende öffentliche Imports, sofern keine bewusste
  Migration dokumentiert ist.

## Nächste sinnvolle Schnitte

`ui.main_window` und `services.metadata_io` sind weiterhin groß. Sie werden in
kleinen, getesteten Schritten entlang tatsächlicher Verantwortungen zerlegt:
Tagger-Aktionen und Workspace-Navigation einerseits, formatspezifische
Metadaten-Adapter andererseits. Der Player erhält in 0.8.5 ein eigenes Paket
und wird nicht in `MainWindow` implementiert.

Die globale Windows-Mediensteuerung liegt getrennt in
`player/windows_media_keys.py`. Sie übersetzt native Hotkey- und
`APPCOMMAND`-Ereignisse in Aufrufe der Player-Engine und verwaltet deren
Registrierungslebenszyklus.

`player/windows_smtc.py` veröffentlicht Metadaten, Cover und Wiedergabestatus
über Windows `SystemMediaTransportControls`. Ist diese optionale Brücke aktiv,
ersetzt sie den nativen Hotkey-Filter; andernfalls bleibt dieser als Fallback
zuständig.

Lokale SQLite-Caches werden über `database.connect_database` geöffnet. Die
gemeinsame Wartezeit verhindert sofortige `database is locked`-Fehler bei
kurzen parallelen Schreibzugriffen. Dateinamen-Fallbacks und lokale
Tracklängen liegen fachlich gebündelt in `local_track.py`.

`theme.py` trennt den Helligkeitsmodus von visuellen Presets. Presets liefern
Paletten und Stylesheets, während `settings.py` nur stabile Preset-IDs
speichert. Widgets verwenden nach Möglichkeit Qt-Palettenrollen, damit
Status- und Auswahlfarben nicht an ein einzelnes Preset gekoppelt sind.

Die statische Typprüfung wird schrittweise über klar abgegrenzte Module
ausgerollt. Der aktuelle Umfang ist in `pyproject.toml` festgelegt und umfasst
26 Domain-, Cache-, Provider-, Lyrics- und Player-Bausteine. `python -m mypy`
prüft damit lokal denselben Bereich wie die CI.

Provider-Client-IDs liegen in der normalen Anwendungskonfiguration. Vertrauliche
Client-Secrets werden dagegen durch `secret_store.py` im Anmeldedatenspeicher
des Betriebssystems abgelegt und weder in `config.toml` noch im Repository
gespeichert.
