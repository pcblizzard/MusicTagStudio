from __future__ import annotations

import re
import tomllib
from pathlib import Path

import musictagstudio

_ROOT = Path(__file__).resolve().parents[1]


def _canonical(version: str) -> str:
    """Vereinheitlicht beide Schreibweisen zu ``0.8.6a26``.

    pyproject/``__version__`` nutzen PEP-440 (``0.8.6a26``), README und
    Changelog die Lesefassung (``v0.8.6-alpha26``). Fuer den Vergleich wird
    ein optionales ``v``-Praefix entfernt und ``-alpha`` zu ``a`` normalisiert.
    """
    return version.strip().lstrip("v").replace("-alpha", "a")


def _pyproject_version() -> str:
    data = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _readme_version(name: str) -> str:
    text = (_ROOT / name).read_text(encoding="utf-8")
    match = re.search(r"v0\.\d+\.\d+-alpha\d+", text)
    assert match, f"Keine Versionsangabe in {name} gefunden"
    return match.group(0)


def _changelog_top_version() -> str:
    text = (_ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^#\s+MusicTagStudio\s+(0\.\d+\.\d+-alpha\d+)", text, re.M)
    assert match, "Oberster Changelog-Eintrag hat kein Versionsformat"
    return match.group(1)


def test_all_version_sources_agree():
    versions = {
        "pyproject.toml": _canonical(_pyproject_version()),
        "__version__": _canonical(musictagstudio.__version__),
        "README.md": _canonical(_readme_version("README.md")),
        "README.de.md": _canonical(_readme_version("README.de.md")),
        "CHANGELOG.md": _canonical(_changelog_top_version()),
    }
    unique = set(versions.values())
    assert len(unique) == 1, f"Versionen weichen ab: {versions}"
