from dataclasses import dataclass


@dataclass
class Song:
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

    comment: str = ""

    path: str = ""

    cover: bytes | None = None