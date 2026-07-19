# Entwicklungsrichtlinien

- Änderungen bleiben klein, testbar und nach Verantwortungen getrennt.
- UI-Module enthalten keine neuen HTTP- oder Dateiformat-Implementierungen.
- Externe Provider werden über klar typisierte Rückgabewerte und eigene
  Fehlerklassen angebunden.
- Metadaten werden vor dem Schreiben angezeigt beziehungsweise verglichen;
  bestehende Dateien werden nicht stillschweigend überschrieben.
- Neue Fehlerfälle erhalten einen Regressionstest. Netzwerk-Tests mocken die
  Provider und benötigen weder Token noch Internetzugriff.
- Öffentliche Importpfade werden bei Verschiebungen durch schmale
  Kompatibilitätsimporte erhalten.
- `config.toml`, Tokens und lokale Medienpfade werden niemals eingecheckt.
- Vor einem Release laufen `python -m pytest`, `python -m compileall -q src`
  und `python scripts/release_check.py`.
