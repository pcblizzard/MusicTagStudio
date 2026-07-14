from dataclasses import dataclass, field
from typing import Literal


SourceName = Literal["local", "apple_music", "musicbrainz"]

EDITABLE_FIELDS: tuple[str, ...] = (
    "title",
    "artist",
    "album_artist",
    "album",
    "genre",
    "year",
    "track",
    "total_tracks",
    "disc",
    "total_discs",
    "isrc",
    "label",
    "copyright",
    "composer",
)

FIELD_LABELS: dict[str, str] = {
    "title": "Titel",
    "artist": "Künstler",
    "album_artist": "Albumkünstler",
    "album": "Album",
    "genre": "Genre",
    "year": "Jahr",
    "track": "Track",
    "total_tracks": "Gesamttracks",
    "disc": "Disc",
    "total_discs": "Gesamt-Discs",
    "isrc": "ISRC",
    "label": "Label",
    "copyright": "Copyright",
    "composer": "Komponist",
}


@dataclass(frozen=True)
class MetadataCandidate:
    source: SourceName
    confidence: int = 0
    title: str = ""
    artist: str = ""
    album_artist: str = ""
    album: str = ""
    genre: str = ""
    year: str = ""
    track: str = ""
    total_tracks: str = ""
    disc: str = ""
    total_discs: str = ""
    isrc: str = ""
    label: str = ""
    copyright: str = ""
    composer: str = ""
    duration_ms: int | None = None
    external_id: str = ""
    release_id: str = ""


@dataclass
class MergedMetadata:
    values: dict[str, str] = field(default_factory=dict)
    sources: dict[str, SourceName] = field(default_factory=dict)
    confidence: dict[str, int] = field(default_factory=dict)

    def changed_fields(self, local_values: dict[str, str]) -> list[str]:
        return [
            name
            for name, value in self.values.items()
            if value and value != local_values.get(name, "")
        ]
