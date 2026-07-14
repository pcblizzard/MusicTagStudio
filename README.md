# MusicTagStudio

MusicTagStudio ist ein Open-Source-Programm zur Verwaltung und Vereinheitlichung von Musiksammlungen.

Der Schwerpunkt liegt auf einer hochwertigen, nachvollziehbaren und möglichst automatisierten Pflege von Metadaten und Albumcovern – ausschließlich über offizielle Schnittstellen der jeweiligen Anbieter.

## Aktueller Status

**Version:** v0.6.0 (Alpha)

Derzeit implementiert:

- Scannen kompletter Musikordner
- Unterstützung mehrerer Audioformate
- Bearbeiten von Metadaten
- Batch-Bearbeitung mehrerer Titel
- Vergleich lokaler Tags mit Online-Metadaten
- Apple Music als bevorzugte Metadatenquelle
- MusicBrainz als Ergänzungsquelle
- Einstellungen für Theme und Datenquellen
- Coververwaltung
- Automatische Covereinbettung
- Album- und Batchvergleich

## Unterstützte Audioformate

- FLAC
- MP3
- Ogg Vorbis
- Opus
- M4A / MP4

Weitere Formate können später ergänzt werden.

## Metadatenquellen

| Anbieter | Status |
|----------|--------|
| Apple Music | ✅ Unterstützt |
| MusicBrainz | ✅ Unterstützt |
| Spotify | 🔴 Noch nicht unterstützt |
| Deezer | 🔴 Noch nicht unterstützt |
| TIDAL | 🔴 Noch nicht unterstützt |
| Amazon Music | 🔴 Noch nicht unterstützt |
| Qobuz | 🔴 Noch nicht unterstützt |
| YouTube Music | 🔴 Noch nicht unterstützt |

## Coverquellen

| Anbieter | Status |
|----------|--------|
| Apple Music | ✅ Unterstützt |
| Cover Art Archive | ✅ Unterstützt |
| Spotify | 🔴 Noch nicht unterstützt |
| Deezer | 🔴 Noch nicht unterstützt |
| TIDAL | 🔴 Noch nicht unterstützt |
| Amazon Music | 🔴 Noch nicht unterstützt |
| Qobuz | 🔴 Noch nicht unterstützt |

## Projektphilosophie

MusicTagStudio verwendet ausschließlich offiziell dokumentierte Programmierschnittstellen.

Es werden keine inoffiziellen APIs, Web-Scraper oder Login-Umgehungen eingesetzt.

## Roadmap

Die geplanten Funktionen befinden sich in:

- docs/ROADMAP.md

## Änderungsverlauf

Alle Versionen:

- docs/CHANGELOG.md