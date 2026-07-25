# Mitgelieferte Binärdateien

## fpcalc (Chromaprint)

Für den akustischen Fingerabdruck (AcoustID) legt MusicTagStudio das
`fpcalc`-Tool hier ab und bevorzugt es gegenüber einer PATH-Installation.

**So einrichten:**

1. Chromaprint von <https://acoustid.org/chromaprint> herunterladen
   (Windows: `chromaprint-fpcalc-*-windows-x86_64.zip`).
2. Die enthaltene `fpcalc.exe` (bzw. unter Linux/macOS `fpcalc`) direkt in
   dieses Verzeichnis kopieren:
   - `src/musictagstudio/providers/vendor/fpcalc.exe`
   - `src/musictagstudio/providers/vendor/fpcalc`

Die App sucht in dieser Reihenfolge:
1. den in den Einstellungen hinterlegten Pfad (`fpcalc_path`),
2. die Datei in diesem Verzeichnis,
3. `fpcalc` im System-PATH.

## AcoustID-API-Key

Der Standard-Key wird in `../fingerprint.py` als `ACOUSTID_APP_KEY` gesetzt.
Registriere dafür einmalig eine Anwendung auf
<https://acoustid.org/new-application> und trage den erhaltenen
*Application API Key* dort ein. Nutzer können ihn in den Einstellungen
überschreiben.

> Hinweis: Binärdateien sind bewusst nicht im Repository eingecheckt.
