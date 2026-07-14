# Changelog

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
