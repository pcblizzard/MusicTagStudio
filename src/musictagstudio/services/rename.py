"""Dateiumbenennung nach konfigurierbarem Schema.

Reine Logik ohne Qt/IO-Nebenwirkungen: aus einem :class:`Song` und einem
Muster wie ``"{track} - {title}"`` wird ein sicherer neuer Dateiname
berechnet. Die Originalendung bleibt immer erhalten; das Muster bestimmt nur
den Namensstamm. :func:`plan_renames` erkennt No-Ops, Kollisionen innerhalb
der Auswahl und bereits vorhandene Zieldateien.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models.song import Song

# Unterstützte Platzhalter -> Song-Feld. Track/Disc werden zusätzlich
# zweistellig aufgefüllt (siehe _values).
_TOKENS: tuple[str, ...] = (
    "track",
    "title",
    "artist",
    "album_artist",
    "album",
    "disc",
    "year",
    "genre",
)

DEFAULT_PATTERN = "{track} - {title}"

# Unter Windows verbotene Zeichen plus Steuerzeichen.
_FORBIDDEN = '<>:"/\\|?*'


def _sanitize(value: str) -> str:
    """Entfernt verbotene/riskante Zeichen aus einem Dateinamens-Stamm."""
    cleaned = "".join(
        "_" if character in _FORBIDDEN or ord(character) < 32 else character
        for character in value
    )
    # Mehrfach-Leerzeichen zusammenfassen, Rand-Punkte/Leerzeichen entfernen
    # (Windows toleriert keine abschließenden Punkte/Leerzeichen).
    cleaned = " ".join(cleaned.split())
    return cleaned.strip().strip(".").strip()


def _pad_number(value: str) -> str:
    """``"1"`` -> ``"01"``; nicht-numerische Werte bleiben unverändert."""
    text = str(value or "").strip()
    # Nur einen führenden Zahlanteil auffüllen ("1/12" -> "01/12" wäre falsch;
    # das Track-Feld enthält hier bereits nur die reine Nummer).
    if text.isdigit():
        return text.zfill(2)
    return text


def _values(song: Song) -> dict[str, str]:
    raw = {token: str(getattr(song, token, "") or "").strip() for token in _TOKENS}
    raw["track"] = _pad_number(raw["track"])
    raw["disc"] = _pad_number(raw["disc"])
    return raw


def build_new_stem(song: Song, pattern: str) -> str:
    """Berechnet den neuen Namensstamm (ohne Endung) für *song*.

    Unbekannte Platzhalter bleiben als Literal stehen; fehlende Felder werden
    zu leerem Text. Ist das Ergebnis nach der Sanitisierung leer, wird der
    bisherige Dateistamm beibehalten (nie ein leerer Name).
    """
    values = _values(song)

    class _Default(dict):
        def __missing__(self, key: str) -> str:  # unbekannter {token}
            return "{" + key + "}"

    try:
        rendered = pattern.format_map(_Default(values))
    except (ValueError, IndexError):
        # Kaputtes Muster (z. B. einzelne "{") -> unverändert lassen.
        rendered = Path(song.path).stem

    stem = _sanitize(rendered)
    return stem or Path(song.path).stem


def build_new_name(song: Song, pattern: str) -> str:
    """Neuer Dateiname inkl. beibehaltener Originalendung."""
    return build_new_stem(song, pattern) + Path(song.path).suffix


@dataclass(frozen=True)
class RenamePlan:
    old_path: str
    new_path: str
    old_name: str
    new_name: str
    applies: bool
    # "ok" | "unchanged" | "collision" | "target_exists" | "no_path"
    reason: str


def plan_renames(songs: list[Song], pattern: str) -> list[RenamePlan]:
    """Erzeugt für jede Datei einen Umbenennungsplan.

    ``applies=True`` nur, wenn sich der Name ändert und weder eine andere
    Auswahl-Datei noch eine bereits existierende Fremddatei kollidiert.
    """
    plans: list[RenamePlan] = []
    # Zielpfade der bereits als anwendbar geplanten Umbenennungen, um
    # Kollisionen innerhalb der Auswahl zu erkennen (case-insensitiv, da
    # Windows-Dateisysteme nicht zwischen Groß-/Kleinschreibung unterscheiden).
    claimed: dict[str, str] = {}
    sources = {str(Path(song.path).resolve()).casefold() for song in songs if song.path}

    for song in songs:
        if not song.path:
            plans.append(RenamePlan("", "", "", "", False, "no_path"))
            continue

        old_path = Path(song.path)
        new_name = build_new_name(song, pattern)
        new_path = old_path.with_name(new_name)
        old_name = old_path.name

        if new_name == old_name:
            plans.append(
                RenamePlan(str(old_path), str(new_path), old_name, new_name, False, "unchanged")
            )
            continue

        target_key = str(new_path.resolve()).casefold()

        if target_key in claimed:
            plans.append(
                RenamePlan(str(old_path), str(new_path), old_name, new_name, False, "collision")
            )
            continue

        # Zieldatei existiert bereits und gehört nicht zur Auswahl (die eigene
        # Quelle wird weiter unten nie getroffen, da new_name != old_name).
        if new_path.exists() and target_key not in sources:
            plans.append(
                RenamePlan(str(old_path), str(new_path), old_name, new_name, False, "target_exists")
            )
            continue

        claimed[target_key] = str(old_path)
        plans.append(
            RenamePlan(str(old_path), str(new_path), old_name, new_name, True, "ok")
        )

    return plans
