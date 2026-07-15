# MusicTagStudio

MusicTagStudio ist ein vorsichtiger, vorschauorientierter Metadaten-Editor für FLAC, MP3, Ogg Vorbis, Opus und M4A/MP4.

## Start

```powershell
python -m pip install -e .
python -m pytest
python -m musictagstudio.main
```

## Cover-Workflow

- Master im Albumordner: `Albumkünstler - Album.front.<ext>`
- Eingebettet: 1000 px, JPEG, Qualität 100
- Künstlerordner: `Albumkünstler - Album_400px.jpg`, 400 px, Qualität 80
- Coverquellen und Zielordner-Ebene werden unter **Einstellungen → Optionen** gespeichert.


## Audio-Analyse

MusicTagStudio kann eine vorhandene lokale FFmpeg-Installation automatisch erkennen.

Die Analyse umfasst derzeit:

- Codec, Container, Abtastrate, Bittiefe, Kanäle, Bitrate und Dauer
- integrierte Lautheit in LUFS
- Loudness Range
- True Peak
- vorsichtiger Clipping-Hinweis
- ReplayGain Track Gain und Track Peak
- optionales Album-ReplayGain
- technischer Albumvergleich mit Abweichungsanzeige

ReplayGain wird zunächst berechnet und nur nach ausdrücklicher Bestätigung in die Dateien geschrieben.


### Verbesserungen in v0.6.4

- Vier parallele FFmpeg-Analysen auf geeigneten Systemen
- Dauerhafter Analyse-Cache für unveränderte Dateien
- Differenzierte True-Peak-Hinweise statt vollflächiger Warnzeilen
- Durchschnittliche Album-Bitrate und durchschnittliche Album-Lautheit
- Album-ReplayGain und Album-Peak in der Vergleichsansicht
- Erster Album-Gesundheitswert
- Analyseverlauf mit Cache-, Erfolgs- und Fehlermeldungen


### Verbesserungen in v0.6.5

- Realistischere True-Peak-Einordnung: bis 1 dBTP unauffällig
- Gesundheitswert wird bei leicht erhöhten Peaks deutlich weniger streng bewertet
- Sichtbare Cache-, Neuberechnungs- und Zeitstatistik
- Lesbareres Analyseprotokoll
- Fortschrittsdialog beim Schreiben von ReplayGain-Tags
- Einstellbare Anzahl paralleler FFmpeg-Analysen


### Verbesserungen in v0.6.6

- Qualitätsbewertung für Cover von 0 bis 100
- MD5-Vergleich zwischen vorhandenem Master und Online-Covern
- Anzeige identischer Inhalte, unterschiedlicher Auflösungen und abweichender Bilder
- Automatische Empfehlung des besten Covers
- Mehrere ausgewählte Alben können gemeinsam verarbeitet werden
- Vorhandene Master-Cover werden ohne erneuten Download wiederverwendet
- Fehler eines Albums stoppen die Verarbeitung der übrigen Alben nicht


### Bibliotheksprüfung in v0.6.7

Der neue Menüpunkt **Bibliotheksprüfung** kontrolliert markierte oder alle
gescannten Titel auf:

- doppelte ISRCs
- uneinheitliche Albumkünstler, Alben, Genres, Jahre und Labels
- fehlende, doppelte oder lückenhafte Tracknummern
- uneinheitliche Disc- und Track-Gesamtzahlen
- fehlende oder unterschiedliche eingebettete Cover
- fehlende ReplayGain-Track- und Albumwerte

Die Ergebnisse können nach Fehlern, Warnungen und Informationen gefiltert werden.


### Korrektur in v0.6.7.1

- Tracknummern werden jetzt pro Disc geprüft.
- Gleiche Tracknummern auf unterschiedlichen Discs gelten nicht als Duplikat.
- Doppelte Tracknummern werden einzeln und mit den betroffenen Dateien angezeigt.
- Lücken werden pro Disc berechnet.
- Die Detailansicht zeigt alle betroffenen Dateipfade.


### Korrektur in v0.6.7.2

- Direkte Albumzuordnung verwendet eindeutige Titel vor vorhandenen Tracknummern.
- Bereits falsch getaggte Tracknummern können dadurch korrekt ersetzt werden.
- Disc- und Tracknummer dienen nur noch als zweite Zuordnungsstufe.
- Remix- und Instrumentalzusätze bleiben bei der Titelzuordnung erhalten.


### Neue Albumzuordnung in v0.6.7.3

- Vollständige globale Eins-zu-eins-Zuordnung statt einzelner Greedy-Treffer
- Bewertungsmatrix über lokale Dateien und alle Quelltracks
- Dateiname, Titel, Disc-/Tracknummer, Dauer und Reihenfolge werden gemeinsam bewertet
- Nummernpräfixe wie `109.` werden als Disc 1 / Track 09 erkannt
- Manuell korrigierbare Zuordnung vor dem Metadatenvergleich
- Der Vergleich ist erst möglich, wenn jede Datei genau einmal zugeordnet ist
- Sicherheit und Begründung jeder automatischen Zuordnung werden angezeigt


### Korrekturen in v0.6.7.4

- Die normale Batch-Suche bewertet Apple-Music-Treffer jetzt zusätzlich nach Tracknummer, Discnummer, Audiodauer und Dateinamentitel.
- Versionszusätze wie Remix, Instrumental, Live oder Edit werden bei der Titelsuche ausdrücklich berücksichtigt.
- Ein Remix kann dadurch nicht mehr allein wegen eines ähnlichen Grundtitels auf die normale Albumfassung zurückfallen.
- Unterschiedliche MusicBrainz-Albumwerte werden mit Wert und Häufigkeit angezeigt, zum Beispiel `1997 (20×), 2024 (2×)`.
- Gemischte Albumwerte bleiben aus Sicherheitsgründen von einer albumweiten Übernahme ausgeschlossen; die konkreten Einzelwerte stehen im Tab „Individuelle Trackwerte“.


### Korrekturen in v0.6.7.5

- Batch-Abfragen suchen Apple Music zuerst albumweise statt jeden Titel isoliert.
- Die vollständige offizielle Apple-Trackliste wird einmal geladen und global den lokalen Dateien zugeordnet.
- Track 7 kann dadurch nicht versehentlich Track 1 oder Track 11 erhalten.
- Unsichere Einzeltrack-Treffer unter 65 % werden nicht mehr automatisch vorgeschlagen.
- Der konfigurierte Apple-Store wird bevorzugt; ein US-Store-Fallback wird nur bei fehlendem sicheren Albumtreffer verwendet und sichtbar gemeldet.
- Gemischte Werte zeigen nicht mehr `<leer>`, sondern beispielsweise `fehlt bei 1 Titel`.


### Korrekturen in v0.6.7.6

- Apple-Albumtracklisten werden über mehrere Store-Varianten verglichen; verwendet wird die Trackliste mit der besten tatsächlichen Zuordnung.
- Eine unvollständige Store-Trackliste kann dadurch nicht mehr einzelne Titel wie „Minimum“ verlieren.
- Nach erfolgreicher Albumauflösung wird nicht mehr auf eine unabhängige, potenziell falsche Song-Suche zurückgefallen.
- MusicBrainz wird im Batch ebenfalls albumweise geladen und global zugeordnet.
- Kürzere MusicBrainz-Titelvarianten wie „Fenster zum Hof (remix)“ bleiben dadurch sichtbar, auch wenn der lokale oder Apple-Titel ausführlicher ist.


### Korrekturen in v0.6.7.7

- Fehlende Titel in einer unvollständigen Apple-Album-Lookup-Antwort werden streng innerhalb derselben `collectionId` nachgesucht.
- Die Wiederherstellung akzeptiert nur dieselbe Album-ID, Discnummer und Tracknummer.
- Der konfigurierte Store und der US-Store werden für diese albumgebundene Suche geprüft.
- Sobald ein Album sicher erkannt ist, darf die allgemeine Song-Suche keinen ähnlich klingenden, aber falschen Titel mehr einsetzen.
- Apple-Track-IDs aus Album-Lookups bleiben erhalten.


### Korrektur in v0.6.7.8

- Bei MusicBrainz gelten nur tatsächlich zugeordnete Albumtracks als abgeschlossen.
- Nicht sicher zugeordnete Titel werden anschließend zusätzlich einzeln gesucht.
- Ein teilweise passendes Release blockiert dadurch nicht mehr die MusicBrainz-Daten für die übrigen Titel.
- Leere MusicBrainz-Spalten bei vorhandenen Titeldaten werden vermieden.


## v0.6.8.0

### Unabhängige Metadatenquellen

Apple Music und MusicBrainz werden immer unabhängig voneinander abgefragt.
Die bevorzugte Quelle bestimmt nur die Vorauswahl im Vergleichsdialog. Sie
entscheidet nicht mehr, ob eine andere unterstützte Quelle abgefragt wird.

Jede Quelle erhält intern einen eigenen Status und einen eigenen Kandidaten:

- Treffer
- kein Treffer
- Fehler
- nicht abgefragt

Damit kann ein fehlender oder unsicherer Apple-Treffer MusicBrainz nicht
unterdrücken und umgekehrt.

### WavPack-Unterstützung

`.wv`-Dateien werden jetzt vollständig unterstützt:

- Ordnerscan
- Lesen und Schreiben von APEv2-Metadaten
- Track- und Discnummern einschließlich Gesamtzahlen
- Titel, Künstler, Albumkünstler, Album, Genre und Jahr
- ISRC, Label, Copyright, Komponist und Kommentar
- eingebettete Frontcover über `Cover Art (Front)`
- ReplayGain-Tags
- Audioanalyse über FFmpeg/ffprobe
- Bibliotheksprüfung und Coververgleich

WavPack 5 mit DXD 32 Bit / 352,8 kHz benötigt keine besondere Behandlung.
Die technischen Audiodaten werden weiterhin von ffprobe ausgelesen.


### Korrekturen in v0.6.8.1

- WavPack-Tags werden direkt aus APEv2 gelesen und geschrieben.
- Das Tagging hängt nicht mehr davon ab, ob Mutagen den ungewöhnlichen
  WavPack-Audiostream vollständig analysieren kann.
- Das betrifft insbesondere DXD-Dateien mit 32 Bit und 352,8 kHz.
- Der Scan zeigt jetzt erkannte, eingelesene und übersprungene Dateien samt
  konkreter Fehlermeldung an.
- Apple-Music-Song-Links werden als eigene Referenz erkannt.
- Für genau eine markierte Datei kann ein exakter Song-Link geladen werden,
  beispielsweise `https://music.apple.com/song/minimum/1859696298`.


### WavPack-Diagnose und Lesefallback in v0.6.8.2

Der WavPack-Leser verwendet nun drei unabhängige Stufen:

1. direkter APEv2-Leser
2. Mutagens WavPack-Leser
3. ffprobe-Metadaten als Lesefallback

Damit können Dateien im Editor erscheinen, selbst wenn Mutagen bei einem
ungewöhnlichen WavPack-Stream einen Parserfehler auslöst. Für Schreibvorgänge
bleibt APEv2 zuständig; ein Schreibfehler wird ausdrücklich gemeldet.

Technische Fehler werden mit vollständigem Python-Traceback protokolliert:

- `logs/scanner.log`
- `logs/wavpack.log`

Die Logdateien entstehen im MusicTagStudio-Projektordner.


### WavPack-Coverkorrektur in v0.6.8.3

WavPack-Cover werden direkt aus dem APEv2-Feld `Cover Art (Front)`
gelesen. Der WavPack-Audiostream wird dafür nicht mehr geparst.

Außerdem wurde ein doppelter und fehlerhafter WavPack-Zweig in der
Cover-Einbettung entfernt. Vorhandene Cover können nun erkannt,
verglichen, ersetzt und erneut eingebettet werden.


### Apple-Music-Korrekturen in v0.6.8.4

- Fehlende Tracks eines erkannten Albums werden zuerst erneut über die
  offizielle Lookup-API geladen.
- Eingestellter Store und US-Store werden geprüft.
- Exakter Abgleich nach Collection-ID, Discnummer und Tracknummer.
- Search-API nur noch als letzter streng gefilterter Rückfall.
- `limit=200` bei Album-Lookups.
- Vollständiges Protokoll unter `logs/apple_music.log`.
- `remastered` wird wie `remaster`, `remixed` wie `remix` behandelt.
