# MusicTagStudio

MusicTagStudio ist ein vorsichtiger, vorschauorientierter Metadaten-Editor und
Musikkatalog für Windows. Die Anwendung verbindet lokale Audiodateien mit
MusicBrainz, Discogs, Apple Music, Deezer, Cover Art Archive und LRCLIB, ohne
Metadaten ungefragt zu überschreiben.

Aktueller Entwicklungsstand: **v0.8.4-beta**

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

### Audioanalyse und Bibliotheksprüfung

- Codec, Container, Abtastrate, Bittiefe, Kanäle, Bitrate und Dauer
- LUFS, Loudness Range, True Peak und ReplayGain über FFmpeg/ffprobe
- Albumvergleich, Analyse-Cache und vorsichtiger Gesundheitswert
- Prüfung auf doppelte ISRCs, inkonsistente Albumwerte, Tracknummernlücken,
  Coverabweichungen und fehlende ReplayGain-Werte

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

## Installation und Start

Vorausgesetzt werden Windows und Python 3.12 oder neuer.

```powershell
git clone https://github.com/pcblizzard/MusicTagStudio.git
cd MusicTagStudio
python -m pip install -e .
python -m musictagstudio.main
```

Für Audioanalyse und ReplayGain müssen `ffmpeg` und `ffprobe` installiert und
über `PATH` erreichbar sein. Die übrigen Tagging- und Katalogfunktionen können
auch ohne FFmpeg verwendet werden.

## Einrichtung

Beim ersten Start werden die Musikquellen über **Datei → Einstellungen …**
hinterlegt. Die Konfiguration wird lokal in `config.toml` gespeichert.

Discogs ist optional. Ein persönliches API-Token kann in den Einstellungen
hinterlegt werden. Ohne Token bleiben MusicBrainz, lokale Medien, Lyrics und
die übrigen Funktionen verfügbar. Tokens und lokale Medienpfade gehören nicht
in Git-Commits.

Onlineabfragen werden nach Möglichkeit zwischengespeichert. Explizite Aktionen
wie **Discogs live aktualisieren** oder **LRCLIB live suchen** umgehen den
lokalen Stand bewusst.

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
python -m pip install -e .
python -m pytest
python scripts/release_check.py
```

Die Release-Prüfung kompiliert den Quellcode, führt die vollständige Testsuite
aus und entfernt generierte Python-Caches.

Die wichtigsten Pakete unter `src/musictagstudio/` sind:

- `ui/` – Qt-Oberfläche
- `services/` – Tagging-, Scan- und Anwendungslogik
- `providers/` – externe Metadaten- und Musikdienste
- `media_library/` – MusicBrainz-/Discogs-Katalog
- `lyrics/` – Lyrics-Modell, LRCLIB, LRC, Cache und Einbettung
- `audio_analysis/` – technische Audioanalyse
- `library_audit/` – Bibliotheksprüfung
- `models/` und `core/` – gemeinsame Datenmodelle und Regeln

Weitere Hinweise stehen in der
[Architekturdokumentation](docs/ARCHITECTURE.md) und den
[Entwicklungsrichtlinien](docs/CODING_GUIDELINES.md).

## Versionsstand

### v0.8.3

- MusicBrainz und Discogs zusammengeführt
- Discogs-Token, lokaler SQLite-Cache und bewusste Live-Aktualisierung
- exakte Discogs-Künstler- und Labelauflösung
- Labeldiskografien und abgeleitete Künstlerlisten
- Beziehungen, Aliase und anklickbare Verknüpfungen
- einheitliche lokale Statusspalte und Breadcrumb-Navigation

### v0.8.4-beta

- Lyrics-Modell für synchronisierte und unsynchronisierte Texte
- eingebettete Lyrics und LRC-Dateien lesen
- LRCLIB mit lokalem SQLite-Cache
- sichtbarer Lyrics-Dialog mit Quellenwahl und Statusanzeige
- LRC-Dateien speichern
- bestätigte Einbettung mit Vorschau und Wiederherstellung bei Fehlern
- Live-Version-Warnung, Tastenkürzel und UI-Polishing

Die vollständige Historie befindet sich im [Changelog](docs/CHANGELOG.md).

## Roadmap

- Abschluss und stabile Freigabe von v0.8.4
- v0.8.5: interner Player auf Basis der vorhandenen Cover-, Tracklisten- und
  Lyrics-Funktionen

Details und ältere Meilensteine stehen in der [Roadmap](docs/ROADMAP.md).

## Lizenz

Siehe [LICENSE](LICENSE).
