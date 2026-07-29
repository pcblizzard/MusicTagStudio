"""Erzeugt aus einem quadratischen PNG das App-Icon (Multi-Size .ico).

Ablage-Ziel ist ``src/musictagstudio/assets/app.ico`` – von dort nutzen es
Fenster (main._apply_app_icon), PyInstaller-Spec (Exe-Icon) und optional das
Inno-Setup automatisch.

Nutzung (aus dem Repository-Wurzelordner):
    py -3 -m pip install pillow
    py -3 packaging/make_icon.py pfad/zu/logo.png

Das Quell-PNG sollte quadratisch und möglichst groß sein (>= 256x256).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    if len(sys.argv) != 2:
        print("Aufruf: python packaging/make_icon.py <logo.png>")
        return 2
    source = Path(sys.argv[1])
    if not source.is_file():
        print(f"Quelldatei nicht gefunden: {source}")
        return 1

    target = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "musictagstudio"
        / "assets"
        / "app.ico"
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    image = Image.open(source).convert("RGBA")
    if image.width != image.height:
        print(
            f"Hinweis: Bild ist nicht quadratisch ({image.width}x{image.height}) – "
            "es wird nicht zugeschnitten, das Icon könnte verzerrt wirken."
        )
    image.save(target, format="ICO", sizes=SIZES)
    print(f"App-Icon geschrieben: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
