from __future__ import annotations
import json,re
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from .models import CoverCandidate

TIMEOUT=20
USER_AGENT="MusicTagStudio/0.6.0 (https://github.com/pcblizzard/MusicTagStudio)"


def search_apple_cover(album: str, artist: str, country: str="DE") -> list[CoverCandidate]:
    params={"term":" ".join(x for x in (artist,album) if x),"country":country,"media":"music","entity":"album","limit":20}
    payload=_json(f"https://itunes.apple.com/search?{urlencode(params)}")
    result=[]
    for item in payload.get("results",[]):
        url=str(item.get("artworkUrl100") or "")
        if not url: continue
        high=re.sub(r"/\d+x\d+bb\.","/3000x3000bb.",url)
        score=100 if str(item.get("collectionName","")).casefold()==album.casefold() else 70
        result.append(CoverCandidate("apple_music","Apple Music",high,3000,3000,"image/jpeg",str(item.get("collectionId","")),score))
    return sorted(result,key=lambda c:-c.score)


def search_caa_cover(album: str, artist: str) -> list[CoverCandidate]:
    query=f'release:"{_escape(album)}"'
    if artist.strip(): query+=f' AND artist:"{_escape(artist)}"'
    releases=_json(f"https://musicbrainz.org/ws/2/release?{urlencode({'query':query,'fmt':'json','limit':10})}").get("releases",[])
    result=[]
    for release in releases:
        rid=str(release.get("id") or "")
        if not rid: continue
        try: data=_json(f"https://coverartarchive.org/release/{rid}")
        except Exception: continue
        for image in data.get("images",[]):
            if not image.get("front"): continue
            url=str(image.get("image") or "")
            if url: result.append(CoverCandidate("cover_art_archive","Cover Art Archive",url,0,0,"",rid,int(release.get("score") or 0)))
            break
    return sorted(result,key=lambda c:-c.score)


def download(url: str) -> bytes:
    request=Request(url,headers={"User-Agent":USER_AGENT,"Accept":"image/*"})
    with urlopen(request,timeout=TIMEOUT) as response: return response.read()


def _json(url: str) -> dict:
    request=Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
    try:
        with urlopen(request,timeout=TIMEOUT) as response: return json.load(response)
    except (HTTPError,URLError,TimeoutError,json.JSONDecodeError) as error:
        raise RuntimeError(f"Coverquelle konnte nicht abgefragt werden: {error}") from error


def _escape(value: str) -> str:
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/])',r'\\\1',value.strip())
