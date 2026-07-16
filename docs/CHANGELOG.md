# Changelog

## v0.7.2

### Oberfläche

- feste Workspace-Navigation
- direkte Bereiche für Tagger, Medienbibliothek, Audio-Analyse,
  Bibliotheksprüfung und Einstellungen

### Medienbibliothek

- MusicBrainz-Künstlersuche
- Discografie als Release-Gruppen
- Editionen mit Datum, Land, Status, Format, Medien- und Trackzahl
- Tracklisten mit Disc- und Tracknummern
- manueller Apple-Music-Verfügbarkeitscheck
- lokaler Abgleich mit dem aktuellen Scan
- lokales Album im Tagger öffnen
- Qualitätsabfragen nur auf Knopfdruck

### Audioformate

- Monkey's Audio (`.ape`)
- WMA/ASF (`.wma`, `.asf`)
- M4B (`.m4b`)

### BBCode

- Künstlerordner anhand des Albumkünstlernamens robust ermittelt



## v0.7.1.6

### Coverdialog

- Möglichen nativen Absturz durch späte QRunnable-Rückrufe behoben
- Globalen Thread-Pool durch dialogeigenen Pool ersetzt
- Aktive Worker werden bis zu ihrem Abschluss referenziert
- Closure-basierte Widget-Rückrufe durch gebundene Qt-Slots ersetzt
- Ergebnisse nach dem Schließen werden verworfen
- Vorschau-Prefetch auf den gewählten und zwei weitere Treffer begrenzt
- Diagnoseprotokoll `logs/cover.log` ergänzt



## v0.7.1.5

### BBCode-Text

- Tracklisten nach CDs gruppiert
- CD-Überschriften im Format `[b]CD1[/b]:`
- Originale Apple-Music-Tracktitel werden für die Ausgabe geladen
- Lokale, normalisierte Artist-Tags bleiben unverändert
- Sicherer Fallback auf lokale Titel
- Links-Platzhalter ohne zusätzlichen Image-BBCode

### Haupttabelle

- Track- und Discnummern zweistellig formatiert
- Beispiele: `01/27`, `02/27`, `01/02`



## v0.7.1.4

### Auswahl und Editor

- Falsche Warnung zu ungespeicherten Änderungen behoben
- `comment` zu `EDITABLE_FIELDS` ergänzt
- Feldbezeichnung „Kommentar“ zentral ergänzt
- Ausgangswerte und aktuelle Editorwerte besitzen wieder dieselben Felder
- Titelwechsel, Mehrfachauswahl und Strg+A lösen ohne echte Änderung keine
  Speicherabfrage mehr aus



## v0.7.1.3

### Kritischer Startfehler

- `comment` war in `OPTIONAL_FIELDS`, aber nicht in `table_fields` enthalten
- dadurch scheiterte `update_optional_columns()` beim Programmstart
- Kommentarspalte vollständig ergänzt
- GUI-Smoke-Test für die Erzeugung des Hauptfensters hinzugefügt



## v0.7.1.2

### Hauptfenster

- COMMENT-Feld als „Kommentar“ ergänzt
- Editorbereich scrollbar gemacht
- Alle Tabellenspalten frei veränderbar
- Spaltenbreiten über QSettings dauerhaft gespeichert
- Menüpunkt zum Zurücksetzen ergänzt

### Audioanalyse

- Absturz in closeEvent behoben
- Bereits gelöschte Qt-Threadobjekte werden sicher erkannt
- Threadreferenz wird nach finished auf None gesetzt
- Schließen und Abbrechen gegen RuntimeError abgesichert



## v0.7.1.1

### BBCode-Textvorlage

- Fehlerhafte Aktivierungslogik des Buttons korrigiert
- Status wird unmittelbar nach dem Scan aktualisiert
- Status wird bei jeder Auswahländerung aktualisiert
- Funktioniert bei Einzelwahl, Mehrfachwahl und Strg+A
- Mehrere Alben in einer Auswahl werden zuverlässig erkannt
- Aussagekräftige Tooltips bei deaktiviertem Button
- Beschriftung in „BBCode-Text erstellen“ geändert



## v0.7.1

### Coverdialog

- Vorschaubilder werden nach der Suche parallel vorgeladen
- Gemeinsamer RAM-Cache für Vorschaubilder
- Keine doppelten Downloads derselben Vorschau
- Kürzeres Vorschau-Zeitlimit ohne Einfluss auf den Originaldownload

### Metadaten

- Kommentarfeld im Haupteditor ergänzt

### Textvorlage

- Manueller Button zur Erstellung einer BBCode-Textdatei
- Ausgabe im Ordner des 400-px-Covers
- Automatische Tracklist
- Format aus den ausgewählten Audiodateien
- Technische Qualitätsangaben über ffprobe im Hintergrund
- Größe bleibt zur manuellen Ergänzung leer



## v0.7.0

### Workflow

- Automatischer Scan nach Ordnerauswahl
- Scan-Button in „Bibliothek neu einlesen“ umbenannt
- Feldgenaue Änderungsvorschau vor dem Schreiben

### Undo, Redo und Sicherheit

- Rückgängig über Strg+Z und Button
- Wiederholen über Strg+Y/Standard-Redo und Button
- Vollständige Dateisicherungen vor Schreiboperationen
- Undo/Redo für Einzel- und Batch-Tags, direkte Albumabfragen und Cover
- Sitzungsbasierter Änderungsverlauf
- Persistente Manifeste unter `.musictagstudio/history/`

### Internes Testsystem

- Reale Regressionstests für Clueso, Stieber Twins und Remaster-Titel
- Zentrale Release-Prüfung über `scripts/release_check.py`
- GitHub-Actions-Workflow für jeden Push und Pull Request
- Neue Tests für Undo und Redo



## v0.6.8.7

- Alternative Apple-Albumtitel-Suchvarianten
- Collection-ID-Recovery aus bis zu acht markanten Songtreffern
- Mehrheitsentscheidung und Lookup-Validierung
- Prüfung von Albumname und Trackzahl
- Normalisierung vollständiger Datumswerte auf das Jahr
- Ausführliche Recovery-Protokolle



## v0.6.8.6

### Diagnose ab Programmstart

- Protokollierung beginnt vor `QApplication`
- Eindeutige Sitzungs-ID pro Programmstart
- Python-, Betriebssystem-, Pfad- und Prozesseinträge
- Geladene Einstellungen und verwendete Metadatenquelle
- Globale Protokollierung unbehandelter Ausnahmen und Thread-Ausnahmen
- Qt-Meldungen in `logs/qt.log`
- Stabiler Projektordner für Logs und Cache statt abhängigem Arbeitsordner

### Vollständiger Metadaten-Ablauf

- Lokale Eingabedaten jedes markierten Titels
- Bildung der Albumgruppen und ermittelte Albumidentität
- Jede Apple-Albumsuchanfrage
- Alle Albumkandidaten samt Score
- Entscheidung am Mindestscore
- Lookup-Aufrufe und Lookup-Fehler
- Globale Matching-Ergebnisse
- Fehlende lokale Titel
- Exakte Track-Nachsuche und Search-Fallback
- Endergebnis und Warnungen pro Titel



## v0.6.8.5

### Vollständige Apple-Lookup-Diagnose

- Unveränderte Apple-Antworten werden als JSON gespeichert
- Separate Dateien pro Collection-ID und Store
- Jeder Antwort-Eintrag wird protokolliert
- Auch verworfene Einträge erscheinen im Log
- Verwerfungsgründe werden einzeln genannt
- Zusammenfassung über akzeptierte und verworfene Einträge
- Diagnosepfade: `logs/apple_music.log` und `cache/apple/`



## v0.6.8.4

### Apple-Music-Lookup verbessert

- Fehlende Albumtracks werden zuerst per Lookup-API nachgeladen
- Eingestellter Store und US-Store werden geprüft
- Exakter Abgleich nach Collection-ID, Discnummer und Tracknummer
- Search-API nur als letzter streng gefilterter Rückfall
- `limit=200` für Apple-Album-Lookups
- Vollständiges Trackprotokoll in `logs/apple_music.log`

### Versionsnamen normalisiert

- `remastered` entspricht `remaster`
- `remixed` entspricht `remix`



## v0.6.8.3

### WavPack-Cover korrigiert

- Cover werden direkt aus APEv2 gelesen
- `Cover Art (Front)` wird fallunabhängig erkannt
- APEv2-Binärformat mit Dateiname und Null-Trennzeichen wird korrekt zerlegt
- Kein WavPack-Audiostream-Parsing mehr für Cover
- Fehlerhafte doppelte WavPack-Verzweigung in `embed_cover()` entfernt
- WavPack-Cover können korrekt ersetzt und eingebettet werden
- Fehlerdetails werden in `logs/wavpack.log` protokolliert



## v0.6.8.2

### WavPack-Leser weiter abgesichert

- Dreistufiges Lesen über APEv2, Mutagen WavPack und ffprobe
- ffprobe-Tags werden in das gemeinsame Song-Modell übertragen
- DXD-WavPack-Dateien können auch bei einem Mutagen-Parserfehler gescannt werden
- Schreibfehler werden nicht mehr verschluckt
- Vollständige Tracebacks in `logs/wavpack.log`
- Scanner protokolliert jede übersprungene Datei in `logs/scanner.log`
- Scanmeldung verweist auf die technischen Logdateien



## v0.6.8.1

### WavPack-Scan robust gemacht

- Direkter APEv2-Zugriff für `.wv`
- Kein vollständiges Parsen des WavPack-Audiostreams zum Taglesen nötig
- Unterstützung ungewöhnlicher DXD-WavPack-Dateien verbessert
- Detaillierter Scanbericht mit übersprungenen Dateien und Fehlerursachen

### Exakte Apple-Song-Links

- Apple-Song-URLs werden von Album-URLs unterschieden
- Offizieller ID-Lookup für einen einzelnen Apple-Music-Song
- Exakte Song-ID kann einer einzelnen markierten Datei zugeordnet werden



## v0.6.8.0

### Metadatenquellen entkoppelt

- Apple Music und MusicBrainz werden unabhängig voneinander abgefragt
- Bevorzugte Quelle beeinflusst nur noch die Vorauswahl
- Eigenes SourceProposal-Modell pro Anbieter
- Quellenstatus und Kandidaten werden getrennt gespeichert
- Ein fehlender Treffer einer Quelle unterdrückt keine andere Quelle

### WavPack vollständig unterstützt

- `.wv` in der zentralen Liste unterstützter Audioformate
- APEv2-Metadaten lesen und schreiben
- Cover Art (Front) lesen und einbetten
- ReplayGain in APEv2 schreiben
- Bibliotheksprüfung nutzt den zentralen Cover-Leser
- Audioanalyse funktioniert über FFmpeg/ffprobe
- FLAC-spezifische Formulierung im Batchdialog entfernt



## v0.6.7.8

### MusicBrainz-Fallback korrigiert

- Nur erfolgreich zugeordnete Release-Tracks werden als aufgelöst markiert
- Nicht zugeordnete Titel erhalten anschließend die titelweise MusicBrainz-Suche
- Teilweise passende Releases blockieren nicht mehr die restlichen Titel
- Zusätzlicher Hinweis bei nicht eindeutiger Release-Zuordnung



## v0.6.7.7

### Unvollständige Apple-Albumtracklisten abgesichert

- Strenge Nachsuche fehlender Tracks innerhalb einer bekannten collectionId
- Abgleich von collectionId, Discnummer und Tracknummer
- Storeübergreifende Nachsuche im konfigurierten Store und im US-Store
- Kein allgemeiner Song-Fallback mehr, sobald das Album sicher erkannt wurde
- Falsche Ersatztreffer wie „Jedes Jahr“ für „Minimum“ werden dadurch ausgeschlossen
- Apple-Song-IDs werden aus Album-Lookups übernommen
- Aussagekräftige Warnung, falls ein Track auch albumgebunden nicht auffindbar ist



## v0.6.7.6

### Albumtracklisten für Apple Music und MusicBrainz stabilisiert

- Apple-Tracklisten mehrerer Stores werden nach tatsächlicher Zuordnungsabdeckung verglichen
- Vollständigste passende Apple-Trackliste wird verwendet
- Kein Einzeltrack-Fallback nach erfolgreich erkannter Albumquelle
- MusicBrainz-Release-Suche und vollständige Release-Trackliste im Batch
- Globale MusicBrainz-Zuordnung statt exakter Einzelaufnahme-Suche
- MusicBrainz-Anfragen der direkten Release-Abfrage werden rate-limitiert
- Fehlende Quellwerte entstehen nur noch bei wirklich nicht sicher zuordenbaren Titeln



## v0.6.7.5

### Apple-Music-Batchzuordnung korrigiert

- Offizielle Apple-Albumsuche für Batch-Vorschläge
- Vollständige Trackliste wird über die offizielle Lookup-API geladen
- Globale Zuordnung aller ausgewählten Dateien zur Albumtrackliste
- Unabhängige, fehleranfällige Einzeltrack-Suche dient nur noch als Rückfalllösung
- Unsichere Apple-Treffer werden nicht automatisch übernommen
- Transparenter US-Store-Fallback, falls der konfigurierte Store keinen sicheren Albumtreffer liefert
- `<leer>` aus der Mischwertanzeige entfernt
- Fehlende Werte werden verständlich als `fehlt bei … Titel(n)` angezeigt



## v0.6.7.4

### Apple-Music-Trefferauswahl und Quellenanzeige korrigiert

- Apple-Music-Suche berücksichtigt lokale Track- und Discnummer
- Dateinamentitel wird als zusätzliches Signal verwendet
- Audiodauer wird bei vorhandener Datei in die Bewertung einbezogen
- Versionszusätze wie Remix und Instrumental werden stärker gewichtet
- Normale Albumfassung wird bei gewünschtem Remix deutlich abgewertet
- MusicBrainz-Mischwerte zeigen die konkreten Werte samt Häufigkeit
- Gemischte Werte bleiben für albumweite Schreibvorgänge gesperrt



## v0.6.7.3

### Albumzuordnung vollständig neu aufgebaut

- Globale Eins-zu-eins-Zuordnung über eine Bewertungsmatrix
- Ungarischer Algorithmus bestimmt die insgesamt beste Zuordnung
- Dateinamen werden zusätzlich zu vorhandenen Tags ausgewertet
- Dreistellige Präfixe wie 109 werden als Disc 1 / Track 09 interpretiert
- Lokale Titel, Dateinamentitel, Dauer und Reihenfolge fließen in die Bewertung ein
- Falsche lokale Tracktags besitzen nur noch geringe Priorität
- Zuordnungsmatrix ist vor dem Schreiben sichtbar
- Jede Zuordnung kann manuell korrigiert werden
- Doppelte und fehlende Zuordnungen blockieren den Metadatenvergleich
- Sicherheit und Begründung werden pro Datei angezeigt



## v0.6.7.2

### Korrektur der direkten Albumzuordnung

- Eindeutige Titelübereinstimmungen haben Vorrang vor lokalen Tracknummern
- Falsch vorhandene Tracknummern blockieren nicht mehr die korrekte Zuordnung
- Disc- und Tracknummer werden als zweite Zuordnungsstufe verwendet
- Leichte Schreibvarianten werden als zusätzliche dritte Stufe berücksichtigt
- Remix- und Instrumentalzusätze werden nicht entfernt



## v0.6.7.1

### Korrektur der Tracknummernprüfung

- Tracknummern werden jetzt pro Disc geprüft
- Gleiche Tracknummern auf unterschiedlichen Discs sind zulässig
- Doppelte Tracknummern werden einzeln gemeldet
- Betroffene Dateien erscheinen vollständig in der Detailansicht
- Lücken in der Nummerierung werden pro Disc ermittelt
- Track-Gesamtzahlen werden pro Disc verglichen



## v0.6.7

### Bibliotheksprüfung Teil 1

- Neuer Hauptmenüpunkt „Bibliotheksprüfung“
- Prüfung markierter oder aller gescannten Titel
- Erkennung doppelter ISRCs
- Prüfung einheitlicher Albumwerte
- Prüfung von Tracknummern, Discnummern und Gesamtzahlen
- Erkennung fehlender und unterschiedlicher eingebetteter Cover
- Erkennung fehlender ReplayGain-Tags
- Filter nach Fehlern, Warnungen und Informationen
- Detailansicht pro Hinweis
- Erster bibliotheksweiter Gesundheitswert



## v0.6.6

### Coververwaltung verbessert

- Einheitliche Qualitätsbewertung für Cover
- MD5-Hash wird für vollständig geladene Cover berechnet
- Vergleich mit vorhandenem Master-Cover
- Unterscheidung zwischen identischem Inhalt, gleicher Auflösung und abweichendem Bild
- Beste Coverquelle wird automatisch empfohlen
- Mehralbum-Batchverarbeitung
- Vorhandene Master-Cover werden wiederverwendet
- Fehlende Master-Cover werden automatisch gesucht
- Fehler pro Album werden getrennt protokolliert



## v0.6.5

### Audioanalyse verfeinert

- True Peak bis einschließlich 1 dBTP gilt als unauffällig
- Werte über 1 bis 2 dBTP werden als erhöht markiert
- Werte über 2 dBTP werden als kritisch markiert
- Gesundheitswert gewichtet leicht erhöhte Peaks deutlich zurückhaltender
- Statistik zeigt Cache-Treffer, neu berechnete Titel, Gesamtdauer und Durchschnittszeit
- Analyseverlauf wurde lesbarer gestaltet
- Fortschrittsdialog beim Schreiben von ReplayGain-Tags
- Anzahl paralleler Analysen ist unter Einstellungen → Audioanalyse wählbar
- Analyse-Cache wurde wegen der neuen Peak-Einordnung versioniert



## v0.6.4

### Neu und verbessert

- Bis zu vier parallele FFmpeg-Analysen
- Dauerhafter Analyse-Cache unter dem lokalen Benutzerprofil
- Unveränderte Dateien werden bei späteren Durchläufen aus dem Cache geladen
- Cache kann über „Analyse-Cache ignorieren“ bewusst umgangen werden
- True-Peak-Einordnung: unauffällig, erhöht, über 0 dBTP und kritisch
- Nur die True-Peak- und Hinweiszellen werden farblich markiert
- Albumvergleich zeigt durchschnittliche Bitrate und durchschnittliche LUFS
- Album Gain und Album Peak werden angezeigt
- Erster Album-Gesundheitswert von 0 bis 100
- Analyseverlauf mit Angaben zu Cache-Treffern, neuen Analysen und Fehlern
- Album-ReplayGain wird ebenfalls im Analyse-Cache gespeichert



## v0.6.3

### Neu

- Neuer Hauptmenüpunkt „Audio-Analyse“ neben „Einstellungen“
- Automatische Erkennung von ffmpeg und ffprobe
- Technische Analyse von Codec, Container, Abtastrate, Bittiefe, Kanälen, Bitrate und Dauer
- Lautheitsanalyse mit LUFS, Loudness Range und True Peak
- Vorsichtiger Clipping-Hinweis bei True Peak nahe oder über 0 dBTP
- ReplayGain Track Gain und Track Peak
- Optionales gemeinsames Album-ReplayGain
- Albumvergleich mit Erkennung technischer Ausreißer
- Fortschrittsanzeige und Abbruchmöglichkeit
- ReplayGain-Tags für FLAC, MP3, Ogg Vorbis, Opus und M4A/MP4
- Vorhandene ReplayGain-Tags werden nur nach Bestätigung überschrieben



## v0.6.2

### Neu

- Dauerhafter Cover-Suchcache im lokalen Benutzerverzeichnis
- Suchergebnisse bleiben auch nach einem Programmneustart verfügbar
- Cache speichert nur URLs, IDs und Bildmetadaten, keine Bilder oder Zugangsdaten
- Zwischengespeicherte Ergebnisse verfallen standardmäßig nach 30 Tagen
- Schaltfläche „Online neu suchen“ um den Cache bewusst zu umgehen
- Erweiterte Qualitätsanzeige für Cover
- Anzeige von Quelle, Auflösung, Format, Dateigröße, Seitenverhältnis und Bewertung
- Vorschauauflösung und Vorschaugröße werden nach dem Laden angezeigt



## v0.6.1

### Neu

- Cover-Dialog öffnet sich sofort und lädt Ergebnisse im Hintergrund
- Apple Music und Cover Art Archive werden parallel abgefragt
- Kleine Vorschaubilder werden erst bei Auswahl geladen
- Originalcover wird erst beim endgültigen Übernehmen heruntergeladen
- Vorhandenes Master-Cover wird ohne Onlineabfrage sofort angeboten
- Suchergebnisse werden während der Programmsitzung zwischengespeichert
- Direkte Apple-Music-Albumlinks und Album-IDs werden unterstützt
- Direkte MusicBrainz-Release-Links, Release-Group-Links und MBIDs werden unterstützt
- Lokale Titel werden anhand von Disc-, Tracknummer und Titel zugeordnet
- Direkte Albumdaten werden vor dem Speichern in der Batch-Vergleichsansicht geprüft



## 0.6.0

- Coverquellen mit Ampelstatus, Tooltips und dauerhafter Auswahl
- Apple Music und Cover Art Archive als offizielle Coverquellen
- Master-Cover in bestmöglicher Qualität im Albumordner
- 1000-px-JPEG mit Qualität 100 für eingebettete Cover
- 400-px-JPEG mit Qualität 80 im konfigurierbaren übergeordneten Künstlerordner
- Cover-Einbettung für FLAC, MP3, Ogg Vorbis, Opus und M4A/MP4
- Allgemeiner Audioscan statt ausschließlich FLAC
- Mehrfachauswahl zeigt Gesamttracks bei vollständiger Albumauswahl korrekt
- Auswahlstatus zeigt Titel- und Albumanzahl
- Editorbereich besitzt eine feste Breite und wächst nicht mehr mit Feldinhalten



## 0.5.0

- Feldgenaue Quellenwahl auch in der Batch-Vergleichsansicht
- Getrennte Tabs für gemeinsame Albumwerte und individuelle Trackwerte
- Bevorzugte Quelle wird als Standardempfehlung verwendet
- Fehlende Werte können automatisch aus der anderen unterstützten Quelle ergänzt werden
- Konflikte zwischen Apple Music und MusicBrainz werden sichtbar markiert
- Gemeinsame Albumwerte können auf alle markierten Titel angewendet werden
- Tracktitel, Künstler, Tracknummer, Discnummer, ISRC und Komponist bleiben individuell auswählbar
- Nur tatsächlich ausgewählte Änderungen werden gespeichert


## 0.4.1

- Vergleichsansicht zeigt Lokal, Apple Music und MusicBrainz nebeneinander
- Bevorzugte Quelle wird deutlich hervorgehoben
- Ergänzte Felder werden gesondert gekennzeichnet
- Konflikte zwischen Anbietern werden sichtbar markiert
- Quelle kann für jedes Feld einzeln ausgewählt werden
- Nur die tatsächlich ausgewählten Fremdwerte werden in den Editor übernommen


## 0.4.0

- Neues Einstellungsfenster
- Theme-Auswahl: Automatisch, Hell oder Dunkel
- Automatischer Modus orientiert sich an der Windows-Darstellung
- Metadatenquellen mit Statusfarben und erklärenden Tooltips
- Nicht unterstützte Anbieter bleiben sichtbar, aber nicht auswählbar
- Bevorzugte Quelle wird dauerhaft in config.toml gespeichert
- Optionales Ergänzen fehlender Felder durch andere unterstützte Quellen
- Gewählte Quelle besitzt für sämtliche vorhandenen Felder Priorität
- Feature-Behandlung ist über das Einstellungsfenster auswählbar


## 0.3.2

- Gemeinsames Cover bleibt bei Mehrfachauswahl sichtbar
- Coververgleich über Bild-MD5 und technische Eigenschaften
- „Unterschiedliche Cover“ nur bei tatsächlichen Abweichungen
- Mischung aus Dateien mit und ohne Cover wird als Unterschied erkannt


## 0.3.1

- Mehrfachbearbeitung für manuell geänderte Felder
- Gemeinsame Werte werden angezeigt, unterschiedliche Werte als Platzhalter
- Nur tatsächlich bearbeitete Felder werden auf alle markierten Titel angewendet
- Konfigurierbare Feature-Behandlung: artist_only, title_and_artist oder source
- Einzelvergleich übernimmt ausgewählte Vorschläge zuverlässig in den Editor


## 0.3.0

- Regel-Engine für Feature-Künstler, Apostrophe, Genres und Künstlerlisten
- Zusammenführungsschicht mit feldbezogener Quellenpriorität
- MusicBrainz-Provider mit Rate-Limit und aussagekräftigem User-Agent
- Vergleichsansicht „Aktuell ↔ Vorschlag ↔ Quelle“
- Batch-Verarbeitung für markierte Titel
- Neue modulare Struktur mit `core`, `models`, `providers`, `services` und `ui`
- Kompatibilitätsmodule für bisherige Imports
