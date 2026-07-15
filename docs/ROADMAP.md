# Roadmap

Ohne feste Termine.

## Nächste sinnvolle Schritte

- Einstellungen für Hell, Dunkel und Automatisch
- Albumweise Apple-Suche mit weniger Netzwerkanfragen
- MusicBrainz-Detailabfrage für Labels und Komponisten
- Cover Art Archive
- Undo/Redo und Dry-Run-Protokoll
- Dateinamen-Vorschau nach dem festgelegten Schema


## v0.6.3 ✅

- Audio-Analyse über FFmpeg und ffprobe
- Lautheit, True Peak und ReplayGain
- Technischer Albumvergleich
- ReplayGain-Tags nach Bestätigung

## Nächste 0.6.x-Schritte

- Spektrale Analyse und vorsichtiger Hinweis auf mögliche Hochkonvertierung
- Stille am Anfang und Ende
- Dauerhafter Analyse-Cache
- Erweiterter Album-Gesundheitscheck


## v0.6.4 ✅

- Parallele Audioanalyse
- Dauerhafter Analyse-Cache
- Differenzierte True-Peak-Hinweise
- Erweiterter Albumvergleich
- Erster Album-Gesundheitswert
- Analyseverlauf

## Weitere 0.6.x-Schritte

- Spektrale Analyse mit vorsichtiger Bewertung
- Stille am Anfang und Ende
- Gesundheitscheck um Metadaten und Cover erweitern
- Einstellung für die Anzahl paralleler Analysen


## v0.6.5 ✅

- Realistischere Peak-Bewertung
- Neu gewichteter Gesundheitswert
- Cache- und Zeitstatistik
- ReplayGain-Fortschrittsdialog
- Einstellbare Parallelisierung
- Verbessertes Analyseprotokoll

## Nächster Schwerpunkt

v0.6.6 konzentriert sich auf die bestehende Coververwaltung:
Qualitätsvergleich, Hashvergleich, konsistente Mehrfachverarbeitung und
weitere Absicherung des Cover-Workflows.


## v0.6.6 ✅

- Cover-Qualitätsvergleich
- MD5-Vergleich
- Automatische Cover-Empfehlung
- Mehralbum-Batchverarbeitung
- Wiederverwendung vorhandener Master-Cover

## Nächster Schwerpunkt

v0.6.7 beginnt mit der Bibliotheksprüfung:
doppelte ISRCs, fehlende Cover, unterschiedliche Albumwerte,
fehlende ReplayGain-Tags und fehlerhafte Track-/Discnummern.


## v0.6.7 ✅

- Bibliotheksprüfung Teil 1
- Doppelte ISRCs
- Albumwert-Konsistenz
- Track- und Discnummern
- Cover-Konsistenz
- ReplayGain-Vollständigkeit

## Nächster Schwerpunkt

v0.6.8 erweitert die Bibliotheksprüfung um Dateinamenschema,
defekte Audiodateien, Ordnercover, Audioformat-Abweichungen und
weitere technische Konsistenzprüfungen.


## v0.6.7.3 ✅

- Neue globale Albumzuordnung
- Bewertungsmatrix und Eins-zu-eins-Matching
- Dateinamen- und Daueranalyse
- Sichtbare, manuell korrigierbare Zuordnung


## v0.6.7.4 ✅

- Track- und versionsbewusste Apple-Music-Suche
- Dateinamen- und Dauerbewertung in der normalen Batch-Suche
- Sichtbare Verteilung gemischter MusicBrainz-Werte


## v0.6.7.5 ✅

- Albumweise Apple-Music-Batchabfrage
- Globale Trackzuordnung im normalen Batch-Workflow
- Mindestvertrauen für Einzeltrack-Treffer
- Verständliche Anzeige fehlender Mischwerte


## v0.6.7.6 ✅

- Storeübergreifende Apple-Tracklistenwahl
- Albumweises MusicBrainz-Matching
- Kein unsicherer Einzeltrack-Fallback nach Albumauflösung


## v0.6.7.7 ✅

- Strikte Wiederherstellung fehlender Apple-Albumtracks
- collectionId-, Disc- und Trackbindung
- Kein falscher allgemeiner Ersatztreffer bei erkanntem Album


## v0.6.7.8 ✅

- MusicBrainz-Release-Matching mit titelweisem Fallback
- Keine pauschale Sperre mehr für unaufgelöste Titel


## v0.6.8.0 ✅

- Vollständig unabhängige Apple-Music- und MusicBrainz-Ergebnisse
- Eigenes Quellenmodell pro Anbieter
- WavPack/APEv2 lesen und schreiben
- WavPack-Cover und ReplayGain
- WavPack in Scan, Analyse und Bibliotheksprüfung


## v0.6.8.2 ✅

- Mehrstufiger WavPack-Lesefallback
- ffprobe-Metadatenfallback
- Scanner- und WavPack-Diagnoseprotokolle
- Vollständige Tracebacks für reale Dateifehler


## v0.6.8.3 ✅

- WavPack-Cover direkt über APEv2
- Vorhandene Frontcover erkennen
- WavPack-Cover korrekt ersetzen und einbetten


## v0.6.8.4 ✅

- Lookup-basierte Wiederherstellung fehlender Apple-Tracks
- Storeübergreifender Disc-/Trackabgleich
- Apple-Music-Diagnoseprotokoll
- Versionssynonyme für Remaster und Remix
