from .apple_music import AppleMusicProviderError, search_song as search_apple_music
from .musicbrainz import MusicBrainzProviderError, search_song as search_musicbrainz

__all__ = [
    "AppleMusicProviderError",
    "MusicBrainzProviderError",
    "search_apple_music",
    "search_musicbrainz",
]
