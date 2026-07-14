from dataclasses import dataclass
from typing import Literal
CoverSourceStatus=Literal["supported","setup_required","unsupported"]
@dataclass(frozen=True)
class CoverSourceDefinition:
    source_id:str; name:str; status:CoverSourceStatus; status_text:str; tooltip:str
    @property
    def selectable(self)->bool: return self.status in {"supported","setup_required"}
COVER_SOURCES=(
    CoverSourceDefinition("apple_music","Apple Music","supported","Unterstützt","In MusicTagStudio unterstützt. Nutzt die von der offiziellen iTunes Search API gelieferten Cover-URLs."),
    CoverSourceDefinition("cover_art_archive","Cover Art Archive","supported","Unterstützt","In MusicTagStudio unterstützt. Nutzt die offizielle Cover Art Archive API in Verbindung mit MusicBrainz-Veröffentlichungen."),
    CoverSourceDefinition("tidal","TIDAL","unsupported","Aktuell nicht unterstützt","In MusicTagStudio derzeit nicht implementiert. Es werden ausschließlich offiziell dokumentierte Schnittstellen verwendet."),
    CoverSourceDefinition("qobuz","Qobuz","unsupported","Aktuell nicht unterstützt","In MusicTagStudio derzeit nicht unterstützt. Es wird keine inoffizielle oder umgeleitete Schnittstelle verwendet."),
    CoverSourceDefinition("deezer","Deezer","unsupported","Aktuell nicht unterstützt","In MusicTagStudio derzeit nicht implementiert."),
    CoverSourceDefinition("amazon_music","Amazon Music","unsupported","Aktuell nicht unterstützt","Der offizielle API-Zugang ist derzeit nicht allgemein verfügbar."),
    CoverSourceDefinition("spotify","Spotify","unsupported","Aktuell nicht unterstützt","In MusicTagStudio derzeit nicht implementiert. Eine offizielle Integration würde eine registrierte Spotify-Anwendung erfordern."),
    CoverSourceDefinition("youtube_music","YouTube Music","unsupported","Aktuell nicht unterstützt","In MusicTagStudio derzeit nicht implementiert. Die YouTube Data API ist keine vollständige Musik-Katalog-API."),
)
COVER_SOURCES_BY_ID={item.source_id:item for item in COVER_SOURCES}
