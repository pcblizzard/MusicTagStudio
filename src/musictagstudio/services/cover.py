from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from PIL import Image


@dataclass(frozen=True)
class CoverInfo:
    data: bytes
    mime: str
    width: int
    height: int
    depth: int
    colors: int
    picture_type: int
    md5: str

    @property
    def signature(self) -> tuple[object, ...]:
        return (self.md5,self.mime.casefold(),self.width,self.height,self.depth,self.colors,self.picture_type)


def image_info(data: bytes, mime: str = "") -> CoverInfo:
    with Image.open(BytesIO(data)) as image:
        width,height=image.size
        detected=Image.MIME.get(image.format or "", mime or "image/jpeg")
    return CoverInfo(data=data,mime=detected,width=width,height=height,depth=24,colors=0,picture_type=3,
        md5=hashlib.md5(data,usedforsecurity=False).hexdigest())


def load_cover(filepath: str | Path) -> bytes | None:
    info=load_cover_info(filepath)
    return info.data if info else None


def load_cover_info(filepath: str | Path) -> CoverInfo | None:
    path=Path(filepath); suffix=path.suffix.lower()
    if not path.is_file(): return None
    if suffix==".flac":
        audio=FLAC(path)
        if not audio.pictures: return None
        p=audio.pictures[0]; data=bytes(p.data)
        return CoverInfo(data,str(p.mime or ""),int(p.width or 0),int(p.height or 0),int(p.depth or 0),int(p.colors or 0),int(p.type),hashlib.md5(data,usedforsecurity=False).hexdigest())
    if suffix==".mp3":
        try: tags=ID3(path)
        except ID3NoHeaderError: return None
        frames=tags.getall("APIC")
        return image_info(bytes(frames[0].data),frames[0].mime) if frames else None
    if suffix in {".ogg",".oga",".opus"}:
        audio=OggOpus(path) if suffix==".opus" else OggVorbis(path)
        values=audio.get("metadata_block_picture") or []
        if not values: return None
        p=Picture(base64.b64decode(values[0])); data=bytes(p.data)
        return CoverInfo(data,str(p.mime or ""),int(p.width or 0),int(p.height or 0),int(p.depth or 0),int(p.colors or 0),int(p.type),hashlib.md5(data,usedforsecurity=False).hexdigest())
    if suffix in {".m4a",".mp4"}:
        audio=MP4(path); covers=(audio.tags or {}).get("covr") or []
        return image_info(bytes(covers[0])) if covers else None
    return None


def embed_cover(filepath: str | Path, jpeg_data: bytes) -> None:
    path=Path(filepath); suffix=path.suffix.lower(); info=image_info(jpeg_data,"image/jpeg")
    if suffix==".flac":
        audio=FLAC(path); audio.clear_pictures(); p=Picture(); p.type=3; p.mime="image/jpeg"; p.desc="Front cover"; p.width=info.width; p.height=info.height; p.depth=24; p.data=jpeg_data; audio.add_picture(p); audio.save(); return
    if suffix==".mp3":
        try: tags=ID3(path)
        except ID3NoHeaderError: tags=ID3()
        tags.delall("APIC"); tags.add(APIC(encoding=3,mime="image/jpeg",type=3,desc="Front cover",data=jpeg_data)); tags.save(path,v2_version=3); return
    if suffix in {".ogg",".oga",".opus"}:
        audio=OggOpus(path) if suffix==".opus" else OggVorbis(path)
        p=Picture(); p.type=3; p.mime="image/jpeg"; p.desc="Front cover"; p.width=info.width; p.height=info.height; p.depth=24; p.data=jpeg_data
        audio["metadata_block_picture"]=[base64.b64encode(p.write()).decode("ascii")]; audio.save(); return
    if suffix in {".m4a",".mp4"}:
        audio=MP4(path)
        if audio.tags is None: audio.add_tags()
        audio.tags["covr"]=[MP4Cover(jpeg_data,imageformat=MP4Cover.FORMAT_JPEG)]; audio.save(); return
    raise ValueError(f"Cover-Einbettung für {suffix} wird nicht unterstützt.")


def covers_are_identical(covers: list[CoverInfo | None]) -> bool:
    if not covers: return True
    first=covers[0]
    if first is None: return all(c is None for c in covers)
    return all(c is not None and c.signature==first.signature for c in covers)
