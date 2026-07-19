from __future__ import annotations

from dataclasses import replace
import re

from .discogs import DiscogsRelease
from .service import ArtistCandidate, ReleaseGroup, Track


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


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
        merged[index] = replace(
            current,
            labels=current.labels or discogs_group.labels,
            formats=current.formats or discogs_group.formats,
            badges=tuple(dict.fromkeys((*current.badges, *discogs_group.badges))),
            external_url=current.external_url or discogs_group.external_url,
            cover_url=current.cover_url or discogs_group.cover_url,
            discogs_release_id=(
                current.discogs_release_id or discogs_group.discogs_release_id
            ),
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
    return f"{track.title} — {track.artist}" if track.artist else track.title


def duration(length_ms: int | None) -> str:
    if not length_ms:
        return ""
    seconds = round(length_ms / 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"
