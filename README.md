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


### Apple-Diagnose in v0.6.8.5

Apple-Album-Lookups werden vollständig nachvollziehbar protokolliert.

Bei jeder Abfrage entstehen:

- `logs/apple_music.log`
- `cache/apple/lookup_<Collection-ID>_<Store>.json`

Die JSON-Datei enthält die unveränderte Antwort der offiziellen Lookup-API.
Das Log enthält für jeden einzelnen Eintrag Index, `wrapperType`, `kind`,
Collection-ID, Disc, Track, Song-ID, Titel, vorhandene Schlüssel sowie den
Status „akzeptiert“ oder den exakten Verwerfungsgrund.


### Vollständiges Sitzungsprotokoll in v0.6.8.6

Die Diagnose beginnt jetzt vor der Erstellung von `QApplication` und damit so
früh wie technisch sinnvoll. Pro Programmstart wird eine eindeutige Sitzungs-ID
vergeben.

Neue Protokolle:

- `logs/application.log`: Programmstart, Version, Python, Betriebssystem,
  Pfade, Einstellungen, Theme, Hauptfenster und Programmende
- `logs/qt.log`: Qt-Warnungen und Qt-Meldungen
- `logs/proposal.log`: kompletter Metadaten-Ablauf vom lokalen Titel über
  Albumgruppen, Albumsuche, Kandidatenfilter, Lookup, Matching und Fallbacks
- `logs/apple_music.log`: Apple-Suche und Apple-Lookup im Detail
- `cache/apple/`: unveränderte Lookup-Antworten

Die Log- und Cacheordner werden nun relativ zum echten Projektordner ermittelt.
Dadurch landen reale Programmläufe nicht mehr versehentlich in temporären
pytest-Verzeichnissen oder einem abweichenden Arbeitsverzeichnis.


### Apple-Collection-Recovery in v0.6.8.7

Bei erfolgloser Albumsuche werden mehrere Albumtitel-Varianten geprüft und anschließend Collection-IDs aus mehreren unabhängigen Songtreffern rekonstruiert. Ein einzelner Treffer reicht nicht. Die Mehrheits-ID wird über die Lookup-API sowie Albumname und Trackzahl validiert. Datumswerte wie `2026-02-27` werden für die Albumwertung auf `2026` normalisiert.


## v0.7.0 – Workflow und Sicherheit

- Ordner werden unmittelbar nach der Auswahl automatisch eingelesen.
- Der Scan-Button bleibt als „Bibliothek neu einlesen“ erhalten.
- Änderungen erhalten vor dem Schreiben eine feldgenaue Vorschau.
- Jede Schreiboperation erzeugt vollständige Sicherheitskopien.
- Rückgängig mit `Strg+Z`, Wiederholen mit `Strg+Y` bzw. Standard-Redo.
- Buttons für Rückgängig, Wiederholen und Änderungsverlauf.
- Sitzungsverlauf mit Zeit, Beschreibung und Dateianzahl.
- Undo/Redo umfasst Metadaten, Batch-Vorgänge, direkte Albumabfragen und
  Coveränderungen.
- Reale Regressionsfälle werden dauerhaft als Tests hinterlegt.
- `scripts/release_check.py` führt Compile- und Testprüfung aus.
- GitHub Actions prüft jeden Push und Pull Request unter Python 3.12.

Die Albumversionswahl nutzt weiterhin Trackzahl, Disczahl, Titel, Jahr und das
globale Track-Matching. Eindeutige Versionen werden automatisch gewählt;
mehrdeutige Fälle werden im Vergleich als Konflikt sichtbar, ohne still eine
schlechtere Ausgabe zu überschreiben.


## v0.7.1

### Schnellere Covervorschau

- Vorschaubilder werden unmittelbar nach der Cover-Suche im Hintergrund
  vorgeladen.
- Beim Anklicken einer Quelle liegt die Vorschau deshalb meistens bereits im
  Arbeitsspeicher.
- Vorschauen werden dialogübergreifend nach URL zwischengespeichert.
- Doppelte Downloads derselben Vorschau werden vermieden.
- Für Vorschaubilder gilt ein kürzeres Zeitlimit von acht Sekunden. Der
  Originaldownload beim Übernehmen bleibt davon unberührt.

### Kommentarfeld

- Das bereits intern unterstützte Metadatenfeld `comment` ist jetzt im
  Haupteditor als „Kommentar“ sichtbar und bearbeitbar.
- Lesen und Schreiben funktioniert für FLAC/Vorbis, WavPack/APEv2, MP3/ID3
  sowie MP4/M4A.

### Testweise Textvorlage

- Neuer Button „Textvorlage erstellen“.
- Die Datei wird nur auf ausdrücklichen Knopfdruck erzeugt.
- Sie wird neben dem 400-px-Cover im Künstlerordner gespeichert.
- Dateiname: `Albumkünstler - Albumname.txt`.
- Interpret, Album, Jahr, Genre, Format und Tracklist werden aus den Tags
  übernommen.
- Bit-Tiefe, Abtastrate und durchschnittliche Bitrate werden über schnelle
  ffprobe-Abfragen im Hintergrund ermittelt.
- Das Feld „Größe“ bleibt absichtlich leer.


## v0.7.1.1

- Der Button „BBCode-Text erstellen“ wird nach Scan und Auswahlwechsel
  zuverlässig aktualisiert.
- Die Aktivierung funktioniert auch bei automatisch eingelesenen Ordnern,
  `Strg+A` und bereits unveränderter Auswahl.
- Der Button ist aktiv, sobald mindestens ein Titel aus genau einem Album
  markiert ist.
- Bei leerer Auswahl oder mehreren Alben erklärt ein Tooltip den Grund für
  die Deaktivierung.


## v0.7.1.2

- COMMENT ist im Editor als „Kommentar“ sichtbar.
- Der rechte Editor ist scrollbar.
- Alle Spalten können frei mit der Maus geändert werden.
- Spaltenbreiten werden dauerhaft gespeichert und bei anderen Alben und
  Ordnern wiederhergestellt.
- Unter „Bearbeiten“ können die Standardbreiten wiederhergestellt werden.
- Absturz beim Schließen der Audioanalyse nach bereits gelöschtem QThread
  behoben.


## v0.7.1.3

- Startfehler aus v0.7.1.2 behoben.
- Die optionale Spalte `comment` ist jetzt vollständig in der Tabelle
  registriert.
- Tabellenfeld, Spaltenüberschrift, Zeilenwerte und Standardbreite sind
  konsistent.
- Zusätzlicher GUI-Starttest verhindert eine Wiederholung dieses Fehlers.


## v0.7.1.4

- Falsche Meldung „Ungespeicherte Änderungen“ beim Wechseln oder Markieren
  von Titeln behoben.
- `comment` war zwar im sichtbaren Editor vorhanden, fehlte aber in
  `EDITABLE_FIELDS`.
- Dadurch enthielt der aktuelle Editorwert das Kommentarfeld, der gespeicherte
  Ausgangszustand jedoch nicht. Beide Wörterbücher waren deshalb unmittelbar
  nach dem Laden verschieden.
- Kommentar ist jetzt vollständig in der gemeinsamen Felddefinition und den
  Feldbezeichnungen registriert.


## v0.7.1.5

- Mehrfach-CDs werden in der BBCode-Tracklist mit `[b]CD1[/b]:`,
  `[b]CD2[/b]:` usw. getrennt.
- Für die Tracklist werden nach Möglichkeit die originalen Tracktitel aus dem
  Apple-Music-Katalog geladen. Die normalisierten Künstler-Tags in den Dateien
  bleiben davon unberührt.
- Falls Apple Music nicht sicher erreichbar ist, wird auf die lokalen Titel
  zurückgefallen.
- Der Links-Bereich enthält nur noch `xxxxxxxxxx`, ohne weiteren Bild-BBCode.
- Track- und Discnummern in der Haupttabelle werden zweistellig dargestellt,
  beispielsweise `01/27` und `01/02`.


## v0.7.1.6

- Nativen Absturz im Coverdialog abgesichert.
- Cover-Suche und Vorschauen laufen in einem dialogeigenen Thread-Pool.
- Worker bleiben bis zum Abschluss referenziert.
- Vorschau-Ergebnisse werden nur noch über gebundene Qt-Slots verarbeitet.
- Beim Schließen werden verspätete Rückrufe von Hintergrundaufgaben getrennt.
- Es werden höchstens drei Vorschauen gleichzeitig vorbereitet.
- Neuer Diagnose-Log `logs/cover.log`.


## v0.7.2 – Workspaces und Medienbibliothek

### Neue Bereichsnavigation

Links befindet sich nun eine feste Navigation ohne Dropdown:

- Tagger
- Medienbibliothek
- Audio-Analyse
- Bibliotheksprüfung
- Einstellungen

### Medienbibliothek – erste funktionsfähige Version

- Künstlersuche über MusicBrainz
- Auswahl bei gleichnamigen Künstlern
- Discografie nach Alben, EPs, Singles, Compilations und Live gruppiert
- konkrete Editionen mit Datum, Land, Status und Format
- Eckdaten je Edition: Anzahl der Medien und Titel
- vollständige Tracklisten einschließlich mehrerer CDs
- lokaler Abgleich mit dem aktuell eingelesenen Album
- lokales Album direkt im Tagger öffnen
- Streaming-Abfrage nur auf Knopfdruck
- Apple-Music-Link nach erfolgreicher manueller Prüfung
- Qualitätsabfragen erfolgen niemals automatisch
- unbekannte Qualitätswerte werden nicht geraten

Die Dienstschaltflächen verwenden zunächst die ausgeschriebenen Markennamen.
Offizielle Logo-Dateien werden erst gebündelt, wenn die jeweiligen
Brand-Assets sauber und regelkonform in das Projekt aufgenommen sind.

### Weitere Audioformate

- Monkey's Audio (`.ape`) lesen und schreiben
- WMA/ASF (`.wma`, `.asf`) lesen und schreiben
- M4B-Hörbücher (`.m4b`) über die MP4-Taglogik

### BBCode-Datei

Der Künstlerordner wird nun anhand des Albumkünstlernamens ermittelt. Die
Textdatei landet damit auch bei unterschiedlich tiefen Ordnerstrukturen im
Künstlerordner und nicht im allgemeinen Music-Ordner.
