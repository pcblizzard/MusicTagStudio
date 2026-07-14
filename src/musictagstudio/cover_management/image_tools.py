from __future__ import annotations
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps


def inspect_image(data: bytes) -> tuple[int,int,str]:
    with Image.open(BytesIO(data)) as image:
        return image.width,image.height,(Image.MIME.get(image.format or "") or "application/octet-stream")


def resize_to_jpeg(data: bytes, size: int, quality: int) -> bytes:
    with Image.open(BytesIO(data)) as image:
        image=ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((size,size),Image.Resampling.LANCZOS)
        output=BytesIO(); image.save(output,format="JPEG",quality=quality,optimize=True,subsampling=0)
        return output.getvalue()


def extension_for_mime(mime: str) -> str:
    return {"image/png":"png","image/webp":"webp","image/jpeg":"jpg"}.get(mime.casefold(),"jpg")


def safe_filename(value: str) -> str:
    forbidden='<>:"/\\|?*'
    result=''.join('_' if char in forbidden else char for char in value).strip().rstrip('.')
    return result or 'cover'
