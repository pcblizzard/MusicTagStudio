from __future__ import annotations

from dataclasses import replace
import re
import unicodedata

from .discogs import DiscogsRelease
from .service import ArtistCandidate, ReleaseGroup, Track


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    value = "".join(
        character for character in value if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "", value)


def merge_release_groups(
    musicbrainz_groups: list[ReleaseGroup],
    discogs_groups: list[ReleaseGroup],
) -> list[ReleaseGroup]:
    merged = list(musicbrainz_groups)
    positions = {
        (normalized(group.title), group.first_release_date[:4]): index
        for index, group in enumerate(merged)
    }
    for discogs_group in discogs_groups:
        key = (
            normalized(discogs_group.title),
            discogs_group.first_release_date[:4],
        )
        index = positions.get(key)
        if index is None:
            positions[key] = len(merged)
            merged.append(discogs_group)
            continue
        current = merged[index]
        contributions = list(current.discogs_contributions)
        current_artist = streaming_artist(current.artist, "")
        discogs_artist = streaming_artist(discogs_group.artist, "")
        if not current_artist and discogs_artist and "Künstler" not in contributions:
            contributions.append("Künstler")
        if discogs_group.discogs_release_id and "Editionen" not in contributions:
            contributions.append("Editionen")
        for name, current_value, discogs_value in (
            ("Labels", current.labels, discogs_group.labels),
            ("Formate", current.formats, discogs_group.formats),
            ("Cover", current.cover_url, discogs_group.cover_url),
        ):
            if not current_value and discogs_value and name not in contributions:
                contributions.append(name)
        if discogs_group.badges and "Kategorien" not in contributions:
            new_badges = set(discogs_group.badges) - set(current.badges)
            if new_badges:
                contributions.append("Kategorien")
        merged[index] = replace(
            current,
            artist=current_artist or discogs_artist or current.artist,
            labels=current.labels or discogs_group.labels,
            formats=current.formats or discogs_group.formats,
            badges=tuple(dict.fromkeys((*current.badges, *discogs_group.badges))),
            external_url=current.external_url or discogs_group.external_url,
            cover_url=current.cover_url or discogs_group.cover_url,
            discogs_release_id=(
                current.discogs_release_id or discogs_group.discogs_release_id
            ),
            discogs_contributions=tuple(contributions),
        )
    return sorted(
        merged,
        key=lambda group: (
            group.first_release_date or "9999",
            group.title.casefold(),
        ),
    )


def label_artist_statistics(
    releases: list[DiscogsRelease],
) -> list[tuple[str, int, str, str]]:
    values: dict[str, dict[str, object]] = {}
    for release in releases:
        year = str(release.year or "")[:4]
        for name in release.artists:
            name = str(name or "").strip()
            if not name or normalized(name) in {"various", "unknownartist"}:
                continue
            key = normalized(name)
            entry = values.setdefault(
                key,
                {"name": name, "count": 0, "years": set()},
            )
            entry["count"] = int(entry["count"]) + 1
            if year.isdigit():
                entry["years"].add(year)
    result = []
    for entry in values.values():
        years = sorted(entry["years"])
        result.append(
            (
                str(entry["name"]),
                int(entry["count"]),
                years[0] if years else "",
                years[-1] if years else "",
            )
        )
    return sorted(result, key=lambda item: (-item[1], item[0].casefold()))


def local_status_display(status: str) -> str:
    return {
        "Lokal verfügbar": "🟢 Lokal verfügbar",
        "Externe Quelle nicht erreichbar": "🟡 Externe Quelle nicht erreichbar",
        "Nicht vorhanden": "⚪ Nicht vorhanden",
        "Nein": "⚪ Nicht vorhanden",
    }.get(str(status or ""), "⚪ Nicht vorhanden")


def release_source_details(
    group: ReleaseGroup,
    local_status: str,
    *,
    apple_music_status: str = "not_checked",
) -> tuple[tuple[str, str], ...]:
    """Describe which providers contributed to a release detail view."""
    details: list[tuple[str, str]] = []

    if group.source == "musicbrainz":
        details.append(("MusicBrainz", "Stammdaten und Veröffentlichung"))

    if group.source == "discogs" or group.discogs_contributions:
        if group.source == "discogs":
            contributions = ["Veröffentlichung und Editionen"]
            for name, value in (
                ("Labels", group.labels),
                ("Formate", group.formats),
                ("Kategorien", group.badges),
                ("Cover", group.cover_url),
            ):
                if value:
                    contributions.append(name)
        else:
            contributions = list(group.discogs_contributions)
        details.append(
            (
                "Discogs",
                ", ".join(contributions),
            )
        )

    apple_text = {
        "found": "Verfügbarkeit bestätigt",
        "not_found": "Keine eindeutige Ausgabe gefunden",
    }.get(apple_music_status, "Noch nicht geprüft")
    details.append(("Apple Music", apple_text))

    details.append(("Lokale Bibliothek", local_status_display(local_status)))
    return tuple(details)


def streaming_artist(group_artist: str, selected_artist: str) -> str:
    """Return a useful Apple search artist instead of UI placeholders."""
    candidate = str(group_artist or "").strip()
    placeholder = normalized(candidate)
    if placeholder in {
        "",
        "unknownartist",
        "unbekannterkunstler",
        "variousartists",
        "verschiedeneinterpreten",
    }:
        return str(selected_artist or "").strip()
    return candidate


def category(group: ReleaseGroup) -> str:
    if group.category:
        return group.category
    secondary = {value.casefold() for value in group.secondary_types}
    if "live" in secondary:
        return "Live"
    if "soundtrack" in secondary:
        return "Soundtracks"
    if "compilation" in secondary:
        return "Compilations"
    return {
        "Album": "Alben",
        "EP": "EPs",
        "Single": "Singles",
        "Broadcast": "Sonstiges",
    }.get(group.primary_type, "Sonstiges")


def artist_text(artist: ArtistCandidate) -> str:
    details = [
        value
        for value in (artist.country, artist.artist_type, artist.disambiguation)
        if value
    ]
    return artist.name if not details else f"{artist.name} ({' · '.join(details)})"


def category_order(category_name: str) -> int:
    order = {
        "Alben": 0, "Live": 1, "EPs": 2, "Singles": 3, "Mixtapes": 4,
        "Sampler": 5, "Compilations": 6, "Soundtracks": 7, "Boxsets": 8,
        "Bootlegs": 9, "Sonstiges": 10,
    }
    return order.get(category_name, 99)


def medium_count(formats: tuple[str, ...]) -> int:
    total = 0
    for value in formats:
        match = re.match(r"(\d+)×", value)
        total += int(match.group(1)) if match else 1
    return max(1, total)


def discogs_position(value: str, fallback: int) -> tuple[int, int]:
    text = str(value or "").strip()
    match = re.match(r"(\d+)[-.](\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    numbers = re.findall(r"\d+", text)
    return (1, int(numbers[-1])) if numbers else (1, fallback)


def duration_ms(value: str) -> int | None:
    parts = str(value or "").split(":")
    try:
        if len(parts) == 2:
            return (int(parts[0]) * 60 + int(parts[1])) * 1000
        if len(parts) == 3:
            return (
                int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            ) * 1000
    except ValueError:
        return None
    return None


def type_text(group: ReleaseGroup) -> str:
    values = [group.primary_type, *group.secondary_types]
    return ", ".join(value for value in values if value) or "Unbekannt"


def track_title(track: Track) -> str:
    return f"{track.title} - {track.artist}" if track.artist else track.title


def duration(length_ms: int | None) -> str:
    if not length_ms:
        return ""
    seconds = round(length_ms / 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"
