# Changelog

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
