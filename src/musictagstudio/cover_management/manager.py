from __future__ import annotations
from dataclasses import dataclass,replace
from pathlib import Path
from .image_tools import extension_for_mime,inspect_image,resize_to_jpeg,safe_filename
from .models import CoverCandidate
from .providers import download,search_apple_cover,search_caa_cover
from ..models.song import Song
from ..services.cover import embed_cover
from ..settings import AppSettings

@dataclass(frozen=True)
class CoverWorkflowResult:
    master_path: Path
    folder_cover_path: Path
    embedded_files: int

class CoverManager:
    def __init__(self,settings: AppSettings): self.settings=settings

    def search(self,song: Song) -> list[CoverCandidate]:
        order=[self.settings.selected_cover_source]
        if self.settings.cover_fallback_enabled:
            order += [x for x in ("apple_music","cover_art_archive") if x not in order]
        candidates=[]
        for source in order:
            try:
                if source=="apple_music": candidates.extend(search_apple_cover(song.album,song.album_artist or song.artist,self.settings.apple_country))
                elif source=="cover_art_archive": candidates.extend(search_caa_cover(song.album,song.album_artist or song.artist))
            except Exception:
                continue
        hydrated=[]
        for candidate in candidates[:12]:
            try:
                data=download(candidate.url); width,height,mime=inspect_image(data)
                score=candidate.score + min(width,height)//100 + (10 if width==height else 0)
                hydrated.append(replace(candidate,data=data,width=width,height=height,mime=mime,score=score))
            except Exception: continue
        return sorted(hydrated,key=lambda c:(-c.score,-c.width*c.height))

    def apply(self,candidate: CoverCandidate,songs: list[Song]) -> CoverWorkflowResult:
        if not songs or candidate.data is None: raise ValueError("Kein Cover oder keine Audiodateien ausgewählt.")
        album_dir=Path(songs[0].path).parent
        album_artist=songs[0].album_artist or songs[0].artist or "Unbekannter Künstler"
        album=songs[0].album or album_dir.name
        base=safe_filename(f"{album_artist} - {album}")
        extension=extension_for_mime(candidate.mime)
        master_path=album_dir/f"{base}.front.{extension}"
        master_path.write_bytes(candidate.data)
        embedded=resize_to_jpeg(candidate.data,self.settings.embedded_cover_size,self.settings.embedded_cover_quality)
        count=0
        for song in songs:
            embed_cover(song.path,embedded); count+=1
        artist_folder=album_dir
        for _ in range(max(1,self.settings.artist_folder_levels_up)):
            artist_folder=artist_folder.parent
        artist_folder.mkdir(parents=True,exist_ok=True)
        folder_path=artist_folder/f"{base}_400px.jpg"
        folder_path.write_bytes(resize_to_jpeg(candidate.data,self.settings.folder_cover_size,self.settings.folder_cover_quality))
        return CoverWorkflowResult(master_path,folder_path,count)
