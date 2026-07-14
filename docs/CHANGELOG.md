# Changelog

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
