# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spezifikation für MusicTagStudio.

Baut einen One-Folder-Build (dist/MusicTagStudio/), den anschließend das
Inno-Setup-Skript (installer.iss) zu einem Setup verpackt.

Bauen (aus dem Repository-Wurzelordner):
    py -3 -m pip install pyinstaller
    py -3 -m PyInstaller packaging/musictagstudio.spec --noconfirm

Ergebnis: dist/MusicTagStudio/MusicTagStudio.exe (+ Abhängigkeiten).
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH wird von PyInstaller gesetzt (Ordner dieser .spec-Datei).
REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))  # noqa: F821
SRC = os.path.join(REPO_ROOT, "src")
PKG = os.path.join(SRC, "musictagstudio")

# Optionales App-Icon: packaging/app.ico, falls vorhanden (sonst Standard-Icon).
_icon_candidate = os.path.join(SPECPATH, "app.ico")  # noqa: F821
APP_ICON = _icon_candidate if os.path.isfile(_icon_candidate) else None

# Mitgelieferte, read-only Ressourcen ins Bundle unter musictagstudio/... legen,
# damit Paket-relative Pfade (Path(__file__).parent/"locales") auch frozen
# funktionieren.
datas = [
    (os.path.join(PKG, "locales"), "musictagstudio/locales"),
    (os.path.join(PKG, "assets"), "musictagstudio/assets"),
]
# LICENSE als Info im Bundle (About-Dialog liest project_root()/LICENSE; dort
# nur für die Anzeige, nicht kritisch, wenn abweichend).
_license = os.path.join(REPO_ROOT, "LICENSE")
if os.path.isfile(_license):
    datas.append((_license, "."))

# Qt-Multimedia-FFmpeg-Backend und weitere PySide6-Datendateien mitnehmen.
datas += collect_data_files("PySide6", includes=["**/ffmpeg*", "**/multimedia*"])

hiddenimports = [
    "PySide6.QtSvg",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
]
hiddenimports += collect_submodules("mutagen")


a = Analysis(  # noqa: F821
    [os.path.join(SPECPATH, "MusicTagStudio.py")],  # noqa: F821
    pathex=[SRC],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MusicTagStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI-App: kein Konsolenfenster
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MusicTagStudio",
)
