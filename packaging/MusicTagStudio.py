"""Einstiegspunkt für den PyInstaller-Build.

PyInstaller braucht ein konkretes Startskript. Es ruft nur die reguläre
main()-Funktion des Pakets auf, damit Entwicklungs- und Build-Start identisch
sind.
"""

from musictagstudio.main import main

if __name__ == "__main__":
    main()
