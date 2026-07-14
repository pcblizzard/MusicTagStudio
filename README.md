# MusicTagStudio

MusicTagStudio ist ein sicherer, vorschauorientierter FLAC-Tagger mit austauschbaren Metadatenquellen.

## Start

```powershell
python -m pip install -e .
python -m musictagstudio.main
```

## Tests

```powershell
python -m pytest
```

## Grundsätze

- Apple Music ist die Hauptquelle für Titel-, Album- und Trackdaten.
- MusicBrainz ergänzt insbesondere ISRC und weitere fehlende Angaben.
- Kein Provider schreibt direkt in Dateien.
- Vor jeder Änderung gibt es eine Vergleichsansicht.
