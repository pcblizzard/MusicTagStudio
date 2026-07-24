# MusicTagStudio

[English](README.md) | **Deutsch**

MusicTagStudio ist ein vorsichtiger, vorschauorientierter Metadaten-Editor,
Musikkatalog und lokaler Audioplayer für Windows. Die Anwendung verbindet
lokale Audiodateien mit MusicBrainz, Discogs, Apple Music, Deezer, TheAudioDB,
Cover Art Archive und LRCLIB, ohne Metadaten ungefragt zu überschreiben.

Aktueller Entwicklungsstand: **v0.8.6-alpha2.3**

## Funktionsumfang

### Tagger

- Metadaten einzelner Titel und vollständiger Alben bearbeiten
- Apple Music und MusicBrainz unabhängig vergleichen
- Albumweise Trackzuordnung statt unsicherer Einzeltreffer
- Feldgenaue Vorschau vor jeder Übernahme
- Undo/Redo und Sicherungskopien für Schreibvorgänge
- Cover suchen, vergleichen, speichern und einbetten
- BBCode-Textvorlagen für Alben erzeugen

### Medienbibliothek

- Live-Künstlervorschläge über MusicBrainz und Deezer
- Künstler-, Veröffentlichungs- und Labelsuche
- Discografien, Editionen und Tracklisten
- MusicBrainz-Beziehungen wie Mitglieder, Gruppen, Aliase und Labels
- Discogs-Ergänzungen für Veröffentlichungen, Labels, Formate und Cover
- Lokale Discogs-Datenbank; Live-Aktualisierung nur auf ausdrücklichen Klick
- Anklickbare Breadcrumb-Navigation
- Statusanzeige:
  - 🟢 Lokal verfügbar
  - 🟡 Externe Quelle nicht erreichbar
  - ⚪ Nicht vorhanden
- Erkannte lokale Alben direkt im Tagger öffnen
- Lokale Titel aus der Album-Trackliste per Doppelklick im Player starten
- Sprachabhängige Künstlerbiografien und Albuminformationen mit sichtbarer Quelle
- Apple-Music-Albumtexte als Fallback für eindeutig bestätigte Veröffentlichungen
- Zwischengespeicherte Streaming-Verfügbarkeit über Ansichtswechsel und Neustarts
- Künstlerbilder über Apple Music mit Discogs-Fallback
- Ansichten als Discografie, Tabelle, Coverliste oder Coverraster
- Sortierbare Discografie- und Tabellenansichten
- Gespeicherte Ansichtsart, Covergröße und Bereichsaufteilung

### Lyrics seit v0.8.4

- eingebettete Lyrics aus unterstützten Audiodateien lesen
- synchronisierte und unsynchronisierte LRC-Dateien lesen
- Lyrics über LRCLIB suchen und lokal zwischenspeichern
- gewählte Lyrics atomar als UTF-8-LRC neben der Audiodatei speichern
- Lyrics nach einer Vorher-/Nachher-Vorschau in Audio-Tags einbetten
- bestehende Lyrics nur nach ausdrücklicher Bestätigung ersetzen
- Warnung bei Live-, Concert- und Unplugged-Versionen, wenn nur Lyrics der
  normalen Fassung vorliegen
- wahlweise Klartext- oder LRC-Anzeige
- umschaltbare Text- und Karaoke-Ansicht für synchronisierte Lyrics
- automatische Hervorhebung und Nachführung der aktuellen Karaoke-Zeile

### Player seit v0.8.5

- lokale Titel direkt aus dem Tagger abspielen
- kompakte, dauerhaft erreichbare Playerleiste am unteren Fensterrand
- Wiedergabe/Pause sowie vorheriger und nächster Titel
- Positionsanzeige, Suche innerhalb des Titels, Lautstärke und Stummschaltung
- Wiedergabewarteschlange aus der aktuellen Titelliste
- Albumwarteschlange per Doppelklick aus der Medienbibliothek starten
- Zwei Zufallsarten: mit navigierbarem Verlauf oder bei jedem Sprung neu ausgelost
- Wiederholung eines Titels oder der gesamten Warteschlange
- Cover, Albumname und Zugang zum Warteschlangenfenster direkt in der Playerleiste
- Titel aus der Warteschlange entfernen oder als Nächstes einordnen
- eigenständiges Warteschlangenfenster mit Mehrfachauswahl und Drag-and-drop
- lokale Alben aus der Medienbibliothek an die laufende Warteschlange anhängen
- Lautstärke, Stummschaltung, Zufallsart und Wiederholungsmodus über Neustarts hinweg speichern
- Fehlende Dateien beim Weiterschalten automatisch überspringen
- Leertaste für Wiedergabe/Pause außerhalb von Texteingaben
- globale Windows-Medientasten für Play/Pause, Vor, Zurück und Stop
- Windows-Systemmedienanzeige mit Titel, Künstler, Album und Cover
- Der laufende Titel wird im Tagger und in der Medienbibliothek hervorgehoben

### Audioanalyse und Bibliotheksprüfung

- Codec, Container, Abtastrate, Bittiefe, Kanäle, Bitrate und Dauer
- LUFS, Loudness Range, True Peak und ReplayGain über FFmpeg/ffprobe
- Albumvergleich, Analyse-Cache und vorsichtiger Gesundheitswert
- Prüfung auf doppelte ISRCs, inkonsistente Albumwerte, Tracknummernlücken,
  Coverabweichungen und fehlende ReplayGain-Werte
- Bestätigtes Schreiben berechneter ReplayGain-Werte
- Helle, verständliche Statusfarben für unauffällige, erhöhte und kritische Werte

### Oberfläche und Bedienung

- helles, dunkles oder automatisch gewähltes Erscheinungsbild
- deutsche oder englische redaktionelle Informationen entsprechend App- oder Systemsprache
- eigenständige Arbeitsbereiche für Startseite, Tagger, Medienbibliothek,
  Audioanalyse und Bibliotheksprüfung
- gespeicherte Fensteraufteilungen und kompakte Navigation

## Datenquellen

| Quelle | Verwendung |
| --- | --- |
| Lokale Bibliothek | Audiodateien, Tags, Cover, Lyrics und Wiedergabe |
| MusicBrainz | Künstler, Veröffentlichungen, Editionen und Beziehungen |
| Discogs | Diskografien, Editionen, Labels, Formate, Cover und Künstlerbilder |
| Apple Music | Albumabgleich, Tracklisten, Cover, Verfügbarkeit und redaktionelle Texte |
| Deezer | ergänzende Live-Künstlervorschläge |
| TheAudioDB | sprachabhängige Künstlerbiografien und Albuminformationen |
| Cover Art Archive | zusätzliche Coverkandidaten |
| LRCLIB | synchronisierte und unsynchronisierte Liedtexte |

Onlinequellen werden nur für die jeweils beschriebene Funktion verwendet.
TIDAL, Qobuz, Spotify, Amazon Music und YouTube Music sind derzeit nicht als
vollständige Katalog- oder Streaminganbieter integriert.

## Unterstützte Audioformate

- FLAC
- MP3
- Ogg Vorbis und Opus
- M4A, MP4 und M4B
- WavPack (`.wv`)
- Monkey's Audio (`.ape`)
- WMA und ASF

Einzelne Metadaten- oder Lyrics-Funktionen hängen von den Möglichkeiten des
jeweiligen Containerformats ab. Vor dem Schreiben zeigt MusicTagStudio die
betroffenen Werte und mögliche Einschränkungen an.

## Installation und Start unter Windows

Vorausgesetzt werden Windows und Python 3.12 oder neuer. Empfohlen wird aktuell
**Python 3.13**, da Vorabversionen neuerer Python-Ausgaben möglicherweise noch
nicht von PySide6 unterstützt werden.

```powershell
git clone https://github.com/pcblizzard/MusicTagStudio.git
cd MusicTagStudio
py -3.13 -m pip install --upgrade pip
py -3.13 -m pip install -e .
py -3.13 -m musictagstudio.main
```

Für Audioanalyse und ReplayGain müssen `ffmpeg` und `ffprobe` installiert und
über `PATH` erreichbar sein. Die übrigen Tagging- und Katalogfunktionen können
auch ohne FFmpeg verwendet werden.

Beide Werkzeuge sind im FFmpeg-Paket enthalten:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Danach Terminal und MusicTagStudio neu öffnen und die Installation prüfen:

```powershell
ffmpeg -version
ffprobe -version
```

## Einrichtung

Beim ersten Start werden die Musikquellen über **Datei → Einstellungen …**
hinterlegt. Die Konfiguration wird lokal in `config.toml` gespeichert.

Darüber hinaus lassen sich dort unter anderem Erscheinungsbild, Sprache,
Apple-Music-Land, Coverausgabe und Parallelisierung der Audioanalyse festlegen.

Discogs ist optional. Ein persönliches API-Token kann in den Einstellungen
hinterlegt werden. Ohne Token bleiben MusicBrainz, lokale Medien, Lyrics und
die übrigen Funktionen verfügbar. Tokens und lokale Medienpfade gehören nicht
in Git-Commits.

Onlineabfragen werden nach Möglichkeit zwischengespeichert. Explizite Aktionen
wie **Discogs live aktualisieren** oder **LRCLIB live suchen** umgehen den
lokalen Stand bewusst.

Streaming-Verfügbarkeiten werden dienstneutral abgelegt und derzeit sieben
Tage wiederverwendet. Redaktionelle Informationen besitzen einen eigenen,
länger gültigen Cache.

## Sicheres Arbeiten

- Fremddaten werden zunächst als Vorschlag angezeigt.
- Qualitätswerte werden nicht geraten.
- Metadaten und Lyrics werden nur auf ausdrücklichen Befehl geschrieben.
- Bestehende eingebettete Lyrics benötigen eine Ersetzungsbestätigung.
- Kritische Schreibvorgänge verwenden Sicherungen beziehungsweise eine
  Wiederherstellung bei Fehlern.

Trotzdem empfiehlt sich für eine Musiksammlung immer ein eigenes, geprüftes
Backup.

## Entwicklung und Tests

```powershell
py -3.13 -m pip install -e ".[dev]"
py -3.13 -m pytest
py -3.13 scripts/release_check.py
```

Die Release-Prüfung kompiliert den Quellcode, führt die vollständige Testsuite
aus und entfernt generierte Python-Caches.

Die wichtigsten Pakete unter `src/musictagstudio/` sind:

- `ui/` – Qt-Oberfläche
- `services/` – Tagging-, Scan- und Anwendungslogik
- `providers/` – externe Metadaten- und Musikdienste
- `media_library/` – MusicBrainz-/Discogs-Katalog
- `media_library/streaming/` – Streamingabgleich und dienstneutraler Cache
- `player/` – Player-Engine, Wiedergabeverlauf und Warteschlange
- `lyrics/` – Lyrics-Modell, LRCLIB, LRC, Cache und Einbettung
- `audio_analysis/` – technische Audioanalyse
- `library_audit/` – Bibliotheksprüfung
- `models/` und `core/` – gemeinsame Datenmodelle und Regeln

Weitere Hinweise stehen in der
[Architekturdokumentation](docs/ARCHITECTURE.md) und den
[Entwicklungsrichtlinien](docs/CODING_GUIDELINES.md).

## Versionsstand

### v0.8.6-alpha2.3

- eigenständiges Warteschlangenfenster
- Drag-and-drop-Sortierung und Mehrfachauswahl
- „Jetzt abspielen“, „Als Nächstes“ sowie gemeinsames Entfernen
- lokale Alben an die bestehende Warteschlange anhängen
- globale Medientasten von Tastaturen, Headsets und Bluetooth-Geräten
- Karaoke-Ansicht für synchronisierte Lyrics
- Windows-Systemmedienanzeige mit Wiedergabestatus und Cover

### v0.8.5

- interner Player mit Cover, Position, Lautstärke und dauerhafter Playerleiste
- bearbeitbare Warteschlange, zwei Zufallsarten und Wiederholungsmodi
- echter Vorwärts-/Rückwärtsverlauf und Überspringen fehlender Dateien
- Wiedergabe lokaler Alben direkt aus der Medienbibliothek
- Streaming-Cache und verbesserter Apple-Music-Albumabgleich
- Künstlerbiografien, Albuminformationen und Künstlerbilder
- gespeicherte Ansichten, Playerzustände und Bereichsaufteilungen

### v0.8.4

- Lyrics-Modell für synchronisierte und unsynchronisierte Texte
- eingebettete Lyrics und LRC-Dateien lesen
- LRCLIB mit lokalem SQLite-Cache
- sichtbarer Lyrics-Dialog mit Quellenwahl und Statusanzeige
- LRC-Dateien speichern
- bestätigte Einbettung mit Vorschau und Wiederherstellung bei Fehlern
- Live-Version-Warnung, Tastenkürzel und UI-Polishing

### v0.8.3

- zusammengeführter MusicBrainz-/Discogs-Katalog
- lokaler Discogs-Cache und bewusste Live-Aktualisierung
- Künstler-, Label- und Beziehungsansichten
- lokale Statusspalte und Breadcrumb-Navigation

Die vollständige Historie befindet sich im [Changelog](docs/CHANGELOG.md).

## Roadmap

v0.8.5 ist als stabiler Player-Meilenstein abgeschlossen. v0.8.6 erweitert
darauf aufbauend die Warteschlange, Lyrics-Anzeige und Windows-
Medienintegration. Die nächsten Schritte stehen in der Roadmap.

Details und ältere Meilensteine stehen in der [Roadmap](docs/ROADMAP.md).

## Lizenz

Siehe [LICENSE](LICENSE).
