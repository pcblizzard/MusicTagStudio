# Changelog

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
