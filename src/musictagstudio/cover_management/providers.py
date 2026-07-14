from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import CoverCandidate


TIMEOUT = 15
USER_AGENT = (
    "MusicTagStudio/0.6.1 "
    "(https://github.com/pcblizzard/MusicTagStudio)"
)


def search_apple_cover(
    album: str,
    artist: str,
    country: str = "DE",
    album_id: str = "",
) -> list[CoverCandidate]:
    if album_id:
        url = (
            "https://itunes.apple.com/lookup?"
            + urlencode(
                {
                    "id": album_id,
                    "entity": "album",
                    "country": country,
                }
            )
        )
    else:
        params = {
            "term": " ".join(
                value
                for value in (artist, album)
                if value
            ),
            "country": country,
            "media": "music",
            "entity": "album",
            "limit": 20,
        }
        url = (
            "https://itunes.apple.com/search?"
            + urlencode(params)
        )

    payload = _json(url)
    result: list[CoverCandidate] = []

    for item in payload.get("results", []):
        if (
            item.get("wrapperType") != "collection"
            and item.get("collectionType") != "Album"
        ):
            continue

        artwork = str(
            item.get("artworkUrl100")
            or ""
        )

        if not artwork:
            continue

        original_url = re.sub(
            r"/\d+x\d+bb\.",
            "/3000x3000bb.",
            artwork,
        )
        preview_url = re.sub(
            r"/\d+x\d+bb\.",
            "/400x400bb.",
            artwork,
        )

        exact_album = (
            str(
                item.get(
                    "collectionName",
                    "",
                )
            ).casefold()
            == album.casefold()
        )
        exact_artist = (
            str(
                item.get(
                    "artistName",
                    "",
                )
            ).casefold()
            == artist.casefold()
        )

        score = (
            (65 if exact_album else 35)
            + (25 if exact_artist else 10)
            + 10
        )

        result.append(
            CoverCandidate(
                source="apple_music",
                source_label="Apple Music",
                url=original_url,
                preview_url=preview_url,
                width=3000,
                height=3000,
                mime="image/jpeg",
                release_id=str(
                    item.get(
                        "collectionId",
                        "",
                    )
                ),
                score=score,
                album=str(
                    item.get(
                        "collectionName",
                        "",
                    )
                ),
                artist=str(
                    item.get(
                        "artistName",
                        "",
                    )
                ),
            )
        )

    return sorted(
        result,
        key=lambda candidate: -candidate.score,
    )


def search_caa_cover(
    album: str,
    artist: str,
    release_id: str = "",
    release_group_id: str = "",
) -> list[CoverCandidate]:
    release_ids: list[
        tuple[str, int, str, str]
    ] = []

    if release_id:
        release_ids.append(
            (
                release_id,
                100,
                album,
                artist,
            )
        )
    elif release_group_id:
        payload = _json(
            "https://musicbrainz.org/ws/2/release?"
            + urlencode(
                {
                    "release-group": release_group_id,
                    "fmt": "json",
                    "limit": 25,
                }
            )
        )

        release_ids.extend(
            (
                str(release.get("id", "")),
                int(release.get("score", 90) or 90),
                str(release.get("title", album)),
                _release_artist(release) or artist,
            )
            for release in payload.get(
                "releases",
                [],
            )
            if release.get("id")
        )
    else:
        query = f'release:"{_escape(album)}"'

        if artist.strip():
            query += (
                f' AND artist:"{_escape(artist)}"'
            )

        releases = _json(
            "https://musicbrainz.org/ws/2/release?"
            + urlencode(
                {
                    "query": query,
                    "fmt": "json",
                    "limit": 8,
                }
            )
        ).get("releases", [])

        release_ids.extend(
            (
                str(release.get("id", "")),
                int(release.get("score", 0) or 0),
                str(release.get("title", album)),
                _release_artist(release) or artist,
            )
            for release in releases
            if release.get("id")
        )

    result: list[CoverCandidate] = []

    with ThreadPoolExecutor(
        max_workers=min(6, max(1, len(release_ids))),
    ) as executor:
        futures = {
            executor.submit(
                _caa_release_cover,
                release_id_value,
                score,
                release_album,
                release_artist,
            ): release_id_value
            for (
                release_id_value,
                score,
                release_album,
                release_artist,
            ) in release_ids
        }

        for future in as_completed(futures):
            try:
                candidate = future.result()
            except Exception:
                continue

            if candidate is not None:
                result.append(candidate)

    return sorted(
        result,
        key=lambda candidate: -candidate.score,
    )


def download(
    url: str,
) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/*",
        },
    )

    with urlopen(
        request,
        timeout=TIMEOUT,
    ) as response:
        return response.read()


def _caa_release_cover(
    release_id: str,
    score: int,
    album: str,
    artist: str,
) -> CoverCandidate | None:
    data = _json(
        "https://coverartarchive.org/release/"
        f"{release_id}"
    )

    for image in data.get("images", []):
        if not image.get("front"):
            continue

        original_url = str(
            image.get("image")
            or ""
        )
        thumbnails = image.get(
            "thumbnails",
            {},
        )
        preview_url = str(
            thumbnails.get("500")
            or thumbnails.get("250")
            or original_url
        )

        if not original_url:
            continue

        return CoverCandidate(
            source="cover_art_archive",
            source_label="Cover Art Archive",
            url=original_url,
            preview_url=preview_url,
            width=0,
            height=0,
            mime="",
            release_id=release_id,
            score=score,
            album=album,
            artist=artist,
        )

    return None


def _json(
    url: str,
) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(
            request,
            timeout=TIMEOUT,
        ) as response:
            return json.load(response)
    except (
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as error:
        raise RuntimeError(
            f"Coverquelle konnte nicht abgefragt werden: {error}"
        ) from error


def _escape(
    value: str,
) -> str:
    return re.sub(
        r'([+\-!(){}\[\]^"~*?:\\/])',
        r'\\\1',
        value.strip(),
    )


def _release_artist(
    release: dict,
) -> str:
    credits = release.get(
        "artist-credit",
        [],
    )

    return ", ".join(
        str(
            (
                credit.get("artist")
                or {}
            ).get(
                "name",
                credit.get("name", ""),
            )
        )
        for credit in credits
        if credit
    )
