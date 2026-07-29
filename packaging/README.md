# Installer bauen (Windows)

Der Nutzer bekommt am Ende ein `MusicTagStudio-Setup.exe`, das die App
installiert und eine Desktop-/Startmenü-Verknüpfung auf `MusicTagStudio.exe`
anlegt – **ohne dass Python installiert sein muss**.

Ablauf: **1) PyInstaller baut die App → 2) Inno Setup packt den Build.**

## Voraussetzungen (einmalig)

- Python mit den Projektabhängigkeiten (`pip install -e .` bzw. `pip install pyside6 mutagen cryptography`).
- PyInstaller: `py -3 -m pip install pyinstaller`
- [Inno Setup 7](https://jrsoftware.org/isdl.php) installiert.

## Schritt 1 – App bauen (PyInstaller)

Aus dem **Repository-Wurzelordner**:

```
py -3 -m PyInstaller packaging/musictagstudio.spec --noconfirm
```

Ergebnis: `dist/MusicTagStudio/MusicTagStudio.exe` (+ Qt-DLLs, Sprachen,
Assets). Diesen Ordner einmal starten und testen:

```
dist\MusicTagStudio\MusicTagStudio.exe
```

Nutzerdaten (Konfiguration, Logs, Cache, Lizenz) landen bewusst in
`%LOCALAPPDATA%\MusicTagStudio\`, damit die installierte App auch unter
`C:\Program Files` schreiben kann und ein Update die Daten nicht löscht.

## Schritt 2 – Setup packen (Inno Setup)

Entweder `packaging/installer.iss` in der Inno-Setup-IDE öffnen und **Compile**,
oder per Kommandozeile:

```
"C:\Program Files\Inno Setup 7\ISCC.exe" packaging\installer.iss
```

Ergebnis: `dist/installer/MusicTagStudio-Setup.exe`.

## Optionales App-Icon

Ohne Icon bekommt die Exe das Standard-Icon. Sobald ein Icon vorliegt:

- Eine `app.ico` (Multi-Size, z. B. 16/32/48/256 px) in `packaging/` ablegen.
- Die Spec nimmt sie automatisch für die Exe.
- Für das Setup-Icon in `installer.iss` die Zeile `SetupIconFile=app.ico`
  einkommentieren.

Ein `.ico` lässt sich z. B. aus einem quadratischen PNG erzeugen (viele
Online-Konverter oder ImageMagick: `magick app.png -define icon:auto-resize=256,48,32,16 app.ico`).

## Datenspeicherung: Standard vs. portabel

Im Setup gibt es die Option **„Portabel: Nutzerdaten im Installationsordner
speichern"**:

- **Standard (Häkchen aus):** Konfiguration, Logs, Cache, Lizenz-/Nutzungsdaten
  liegen in `%LOCALAPPDATA%\MusicTagStudio\` – update-fest und auch unter
  `C:\Program Files` beschreibbar.
- **Portabel (Häkchen an):** Der Installer legt eine Datei `portable.flag` neben
  die Exe; die App speichert dann alles in `<Installationsordner>\data\`.
  Sinnvoll für USB-Sticks oder eine in sich geschlossene Installation.
  **Achtung:** nur in einen beschreibbaren Ordner installieren – nicht nach
  `C:\Program Files` (dort ohne Adminrechte kein Schreibzugriff). Das Setup warnt
  in diesem Fall.

Technisch entscheidet die App über `diagnostics._portable_data_root()` anhand
der `portable.flag` neben der Exe.

## Hinweise

- **ffmpeg:** Die Audio-Vorschau nutzt das in PySide6 gebündelte
  Qt-Multimedia-FFmpeg-Backend (von der Spec eingesammelt). Für die
  Audio-*Analyse* (optional) sucht die App zusätzlich ein `ffmpeg`/`ffprobe`
  unter `tools/ffmpeg/` neben der Exe bzw. im PATH – nur nötig, wenn die
  Analyse-Funktionen genutzt werden.
- **Version:** `MyAppVersion` in `installer.iss` bei Releases mitziehen.
- **Signierung:** Für breite Verteilung ohne SmartScreen-Warnung wäre ein
  Code-Signing-Zertifikat nötig (später, optional).
