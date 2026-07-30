from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request

from ..diagnostics import get_diagnostic_logger

from ..models.metadata import MetadataCandidate
from .apple_http import (
    APPLE_USER_AGENT,
    AppleRequestError,
    request_json,
)


SEARCH_ENDPOINT = "https://itunes.apple.com/search"
USER_AGENT = APPLE_USER_AGENT
DEFAULT_COUNTRY = "DE"
DEFAULT_LIMIT = 50
REQUEST_TIMEOUT_SECONDS = 15
MINIMUM_TRACK_CONFIDENCE = 65
MINIMUM_ALBUM_CONFIDENCE = 70

_VERSION_WORDS = {
    "remix",
    "remixed",
    "mix",
    "instrumental",
    "live",
    "edit",
    "version",
    "radio",
    "acoustic",
    "demo",
    "remaster",
    "remastered",
    "mono",
    "stereo",
}

_VERSION_SYNONYMS = {
    "remastered": "remaster",
    "remixed": "remix",
}


class AppleMusicProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppleAlbumCandidate:
    collection_id: str
    album: str
    artist: str
    track_count: int
    year: str
    country: str
    confidence: int
    # Tagesgenaues Veröffentlichungsdatum (ISO), sofern von der API geliefert –
    # für die Vorab-Erkennung. Leer bei Web-Fallback/unbekannt.
    release_date: str = ""


def search_album(
    album: str,
    artist: str = "",
    *,
    expected_track_count: int | None = None,
    wanted_year: str = "",
    country: str = DEFAULT_COUNTRY,
    limit: int = 25,
) -> list[AppleAlbumCandidate]:
    logger = get_diagnostic_logger(
        "apple_music"
    )
    logger.info(
        "ALBUMSUCHE START | Store=%s | Album=%r | Künstler=%r | "
        "Erwartete Tracks=%r | Jahr=%r | Limit=%s",
        country.upper(),
        album,
        artist,
        expected_track_count,
        wanted_year,
        limit,
    )
    terms = [
        part.strip()
        for part in (
            artist,
            album,
        )
        if part.strip()
    ]

    if not terms:
        logger.warning(
            "ALBUMSUCHE ABBRUCH | Store=%s | Grund=keine Suchbegriffe",
            country.upper(),
        )
        return []

    params = {
        "term": " ".join(terms),
        "country": country.upper(),
        "media": "music",
        "entity": "album",
        "limit": max(
            1,
            min(limit, 200),
        ),
        "lang": "de_de",
        "version": 2,
    }
    request = Request(
        f"{SEARCH_ENDPOINT}?{urlencode(params)}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    payload = _request_payload(request)

    raw_results = payload.get(
        "results",
        [],
    )
    logger.info(
        "ALBUMSUCHE ANTWORT | Store=%s | resultCount=%r | "
        "Einträge=%d",
        country.upper(),
        payload.get(
            "resultCount",
            "?",
        ),
        (
            len(raw_results)
            if isinstance(
                raw_results,
                list,
            )
            else -1
        ),
    )
    results: list[AppleAlbumCandidate] = []

    for item in raw_results:
        collection_id = str(
            item.get(
                "collectionId",
                "",
            )
        )

        if not collection_id:
            continue

        actual_album = str(
            item.get(
                "collectionName",
                "",
            )
        )
        actual_artist = str(
            item.get(
                "artistName",
                "",
            )
        )
        actual_track_count = (
            _optional_int(
                item.get(
                    "trackCount"
                )
            )
            or 0
        )
        actual_year = _extract_year(
            str(
                item.get(
                    "releaseDate",
                    "",
                )
            )
        )
        confidence = _album_match_score(
            wanted_album=album,
            wanted_artist=artist,
            expected_track_count=(
                expected_track_count
            ),
            wanted_year=wanted_year,
            album=actual_album,
            artist=actual_artist,
            track_count=actual_track_count,
            year=actual_year,
        )

        logger.info(
            "ALBUMKANDIDAT | Store=%s | Collection-ID=%s | "
            "Album=%r | Künstler=%r | Tracks=%s | Jahr=%r | Score=%s",
            country.upper(),
            collection_id,
            actual_album,
            actual_artist,
            actual_track_count,
            actual_year,
            confidence,
        )

        results.append(
            AppleAlbumCandidate(
                collection_id=collection_id,
                album=actual_album,
                artist=actual_artist,
                track_count=actual_track_count,
                year=actual_year,
                country=country.upper(),
                confidence=confidence,
                release_date=str(item.get("releaseDate", "")),
            )
        )

    ordered = sorted(
        results,
        key=lambda item: (
            -item.confidence,
            abs(
                (
                    expected_track_count
                    or item.track_count
                )
                - item.track_count
            ),
            item.album.casefold(),
        ),
    )
    logger.info(
        "ALBUMSUCHE ENDE | Store=%s | Kandidaten=%d | "
        "Bester=%s",
        country.upper(),
        len(ordered),
        (
            (
                f"{ordered[0].collection_id} | "
                f"{ordered[0].album} | "
                f"Score {ordered[0].confidence}"
            )
            if ordered
            else "kein Treffer"
        ),
    )

    return ordered


def search_album_variants(
    album: str,
    artist: str = "",
    *,
    expected_track_count: int | None = None,
    wanted_year: str = "",
    country: str = DEFAULT_COUNTRY,
    limit: int = 25,
    track_titles: tuple[str, ...] = (),
) -> list[AppleAlbumCandidate]:
    """Search punctuation variants and merge candidates by collection ID."""
    variants: list[str] = []
    for value in (
        album,
        album.replace("/", " "),
        album.replace("/", "-"),
        re.sub(r"[/_-]+", " ", album),
    ):
        value = re.sub(r"\s+", " ", value).strip()
        if value and value.casefold() not in {
            existing.casefold() for existing in variants
        }:
            variants.append(value)

    by_id: dict[str, AppleAlbumCandidate] = {}
    for variant in variants:
        candidates = search_album(
            variant,
            artist,
            expected_track_count=expected_track_count,
            wanted_year=wanted_year,
            country=country,
            limit=limit,
        )
        for candidate in candidates:
            current = by_id.get(candidate.collection_id)
            if current is None or candidate.confidence > current.confidence:
                by_id[candidate.collection_id] = candidate
        if any(
            candidate.confidence >= MINIMUM_ALBUM_CONFIDENCE
            for candidate in candidates
        ):
            break

    ordered = sorted(
        by_id.values(),
        key=lambda candidate: (-candidate.confidence, candidate.album.casefold()),
    )
    if any(candidate.confidence >= MINIMUM_ALBUM_CONFIDENCE for candidate in ordered):
        return ordered

    # Findet die iTunes-Such-API nichts Sicheres, deckt die öffentliche
    # Apple-Music-Websuche auch nicht indexierte Alben ab (nur eine Anfrage).
    _augment_with_web_search(
        by_id,
        album=album,
        artist=artist,
        expected_track_count=expected_track_count,
        wanted_year=wanted_year,
        country=country,
    )
    ordered = sorted(
        by_id.values(),
        key=lambda candidate: (-candidate.confidence, candidate.album.casefold()),
    )
    if any(candidate.confidence >= MINIMUM_ALBUM_CONFIDENCE for candidate in ordered):
        return ordered

    recovered = _recover_album_from_track_searches(
        album=album,
        artist=artist,
        track_titles=track_titles,
        expected_track_count=expected_track_count,
        wanted_year=wanted_year,
        country=country,
    )
    if recovered is not None:
        by_id[recovered.collection_id] = recovered
    return sorted(
        by_id.values(),
        key=lambda candidate: (-candidate.confidence, candidate.album.casefold()),
    )


def search_albums_via_web(
    album: str,
    artist: str = "",
    *,
    expected_track_count: int | None = None,
    wanted_year: str = "",
    country: str = DEFAULT_COUNTRY,
) -> list[AppleAlbumCandidate]:
    """Sucht Alben ausschließlich über die öffentliche Apple-Music-Websuche.

    Anders als search_album_variants wird nicht zuerst die iTunes-Such-API
    befragt. Der Batch-Weg nutzt diese Funktion gezielt, wenn seine eigene
    API-Suche kein Album gefunden hat.
    """
    by_id: dict[str, AppleAlbumCandidate] = {}
    _augment_with_web_search(
        by_id,
        album=album,
        artist=artist,
        expected_track_count=expected_track_count,
        wanted_year=wanted_year,
        country=country,
    )
    return sorted(
        by_id.values(),
        key=lambda candidate: (
            -candidate.confidence,
            candidate.album.casefold(),
        ),
    )


def _augment_with_web_search(
    by_id: dict[str, AppleAlbumCandidate],
    *,
    album: str,
    artist: str,
    expected_track_count: int | None,
    wanted_year: str,
    country: str,
) -> None:
    """Ergänzt Kandidaten aus der Apple-Music-Websuche.

    Die Websuche liefert nur ID, Titel, Künstler und Trackzahl. Bewertet
    wird sie mit derselben Album-Wertung wie die API-Treffer, sodass sich
    beide Quellen konsistent einordnen. Fehler beim Scraping dürfen den
    Haupt-Suchweg niemals unterbrechen.
    """
    from . import apple_music_web

    if not apple_music_web.WEB_SEARCH_ENABLED:
        return

    try:
        web_albums = apple_music_web.search_albums_web(
            album,
            artist,
            country=country,
        )
    except Exception:  # noqa: BLE001 - Scraping darf den Ablauf nie stoppen
        get_diagnostic_logger("apple_music").exception(
            "Apple-Web-Suche unerwartet fehlgeschlagen | Album=%r",
            album,
        )
        return

    for web in web_albums:
        confidence = _album_match_score(
            wanted_album=album,
            wanted_artist=artist,
            expected_track_count=expected_track_count,
            wanted_year=wanted_year,
            album=web.album,
            artist=web.artist,
            track_count=web.track_count,
            year="",
        )
        candidate = AppleAlbumCandidate(
            collection_id=web.collection_id,
            album=web.album,
            artist=web.artist,
            track_count=web.track_count,
            year="",
            country=country.upper(),
            confidence=confidence,
        )
        current = by_id.get(web.collection_id)

        if current is None or candidate.confidence > current.confidence:
            by_id[web.collection_id] = candidate


def _recover_album_from_track_searches(
    *, album: str, artist: str, track_titles: tuple[str, ...],
    expected_track_count: int | None, wanted_year: str, country: str,
) -> AppleAlbumCandidate | None:
    titles = sorted(
        {str(title or "").strip() for title in track_titles if str(title or "").strip()},
        key=lambda title: (-len(_normalize(title)), title.casefold()),
    )[:5]
    if not titles:
        return None
    wanted_album = _normalize(album)
    wanted_artist = _normalize(artist)
    voters: dict[str, set[int]] = {}
    examples: dict[str, MetadataCandidate] = {}
    for index, title in enumerate(titles):
        try:
            results = search_song(title, artist, album, country=country, limit=100)
        except AppleMusicProviderError:
            continue
        for candidate in results:
            candidate_artist = candidate.album_artist or candidate.artist
            candidate_count = _optional_int(candidate.total_tracks)
            if candidate.confidence < MINIMUM_TRACK_CONFIDENCE:
                continue
            if not candidate.release_id or _normalize(candidate.album) != wanted_album:
                continue
            if wanted_artist and _normalize(candidate_artist) != wanted_artist:
                continue
            if expected_track_count is not None and candidate_count is not None and candidate_count != expected_track_count:
                continue
            voters.setdefault(candidate.release_id, set()).add(index)
            examples.setdefault(candidate.release_id, candidate)
    if not voters:
        return None
    ranked = sorted(voters.items(), key=lambda item: (-len(item[1]), item[0]))
    best_id, votes = ranked[0]
    second_votes = len(ranked[1][1]) if len(ranked) > 1 else 0
    minimum_votes = 2 if len(titles) > 1 else 1
    if len(votes) < minimum_votes or len(votes) <= second_votes:
        return None
    example = examples[best_id]
    return AppleAlbumCandidate(
        collection_id=best_id,
        album=example.album or album,
        artist=example.album_artist or example.artist or artist,
        track_count=_optional_int(example.total_tracks) or expected_track_count or 0,
        year=_extract_year(example.year) or wanted_year,
        country=country.upper(),
        confidence=min(99, 85 + len(votes) * 3),
    )


def _album_match_score(
    *,
    wanted_album: str,
    wanted_artist: str,
    expected_track_count: int | None,
    wanted_year: str,
    album: str,
    artist: str,
    track_count: int,
    year: str,
) -> int:
    from .streaming_catalog import loose_album_key

    # Editions-/Artikel-toleranter Titel-Abgleich (global, s. streaming_catalog).
    loose_match = bool(
        loose_album_key(wanted_album)
        and loose_album_key(wanted_album) == loose_album_key(album)
    )
    if loose_match:
        score = 60
    else:
        score = _field_score(
            wanted_album,
            album,
            exact=65,
            contains=38,
        )
    score += _field_score(
        wanted_artist,
        artist,
        exact=25,
        contains=14,
    )

    if (
        expected_track_count is not None
        and track_count > 0
    ):
        difference = abs(
            expected_track_count
            - track_count
        )

        if difference == 0:
            score += 15
        elif loose_match:
            # Gleiches Album, andere Edition -> Trackzahl darf abweichen.
            score -= min(6, difference)
        else:
            score -= min(
                18,
                difference * 3,
            )

    if (
        wanted_year
        and year
        and wanted_year == year
    ):
        score += 5

    return max(
        0,
        min(
            100,
            score,
        ),
    )


def search_song(
    title: str,
    artist: str = "",
    album: str = "",
    *,
    alternate_title: str = "",
    wanted_track: str = "",
    wanted_disc: str = "",
    duration_ms: int | None = None,
    country: str = DEFAULT_COUNTRY,
    limit: int = DEFAULT_LIMIT,
) -> list[MetadataCandidate]:
    query_title = _more_specific_title(
        title,
        alternate_title,
    )
    terms = [
        part.strip()
        for part in (
            artist,
            album,
            query_title,
        )
        if part.strip()
    ]

    if not terms:
        return []

    params = {
        "term": " ".join(terms),
        "country": country.upper(),
        "media": "music",
        "entity": "song",
        "limit": max(
            1,
            min(limit, 200),
        ),
        "lang": "de_de",
        "version": 2,
    }
    request = Request(
        f"{SEARCH_ENDPOINT}?{urlencode(params)}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    payload = _request_payload(request)

    results: list[MetadataCandidate] = []

    for item in payload.get(
        "results",
        [],
    ):
        if (
            item.get("wrapperType") != "track"
            or item.get("kind") != "song"
        ):
            continue

        candidate = _candidate_from_item(
            item,
            wanted_title=title,
            alternate_title=alternate_title,
            wanted_artist=artist,
            wanted_album=album,
            wanted_track=wanted_track,
            wanted_disc=wanted_disc,
            wanted_duration_ms=duration_ms,
        )
        results.append(candidate)

    return sorted(
        results,
        key=lambda item: (
            -item.confidence,
            _number_for_sort(item.disc),
            _number_for_sort(item.track),
        ),
    )



def search_song_in_album(
    title: str,
    artist: str,
    album: str,
    *,
    collection_id: str,
    alternate_title: str = "",
    wanted_track: str = "",
    wanted_disc: str = "",
    duration_ms: int | None = None,
    countries: tuple[str, ...] = ("DE", "US"),
    limit: int = 100,
) -> list[MetadataCandidate]:
    """
    Sucht einen Titel ausschließlich innerhalb eines bereits bekannten
    Apple-Albums.

    Die normale Song-Suche darf ähnliche Titel aus anderen Releases liefern.
    Diese Funktion akzeptiert deshalb nur Ergebnisse, deren collectionId,
    Tracknummer und Discnummer zum bekannten Album passen.
    """
    query_titles = []

    for value in (
        alternate_title,
        title,
    ):
        value = value.strip()

        if value and value not in query_titles:
            query_titles.append(value)

    query_variants: list[list[str]] = []

    for query_title in query_titles:
        for parts in (
            [artist, query_title],
            [query_title],
            [artist, album, query_title],
        ):
            cleaned = [
                part.strip()
                for part in parts
                if part.strip()
            ]

            if cleaned and cleaned not in query_variants:
                query_variants.append(cleaned)

    wanted_track_number = _optional_int(
        wanted_track
    )
    wanted_disc_number = (
        _optional_int(
            wanted_disc
        )
        or 1
    )
    normalized_collection_id = str(
        collection_id
    ).strip()
    results_by_id: dict[
        str,
        MetadataCandidate,
    ] = {}

    for country in _unique_countries(
        countries
    ):
        for terms in query_variants:
            payload = _search_payload(
                terms,
                country=country,
                entity="song",
                limit=limit,
            )

            for item in payload.get(
                "results",
                [],
            ):
                if (
                    item.get("wrapperType") != "track"
                    or item.get("kind") != "song"
                ):
                    continue

                item_collection_id = str(
                    item.get(
                        "collectionId",
                        "",
                    )
                )

                if (
                    not item_collection_id
                    or item_collection_id
                    != normalized_collection_id
                ):
                    continue

                actual_track = _optional_int(
                    item.get(
                        "trackNumber"
                    )
                )
                actual_disc = (
                    _optional_int(
                        item.get(
                            "discNumber"
                        )
                    )
                    or 1
                )

                if (
                    wanted_track_number is not None
                    and actual_track
                    != wanted_track_number
                ):
                    continue

                if (
                    wanted_disc_number
                    != actual_disc
                ):
                    continue

                candidate = _candidate_from_item(
                    item,
                    wanted_title=title,
                    alternate_title=(
                        alternate_title
                    ),
                    wanted_artist=artist,
                    wanted_album=album,
                    wanted_track=(
                        wanted_track
                    ),
                    wanted_disc=(
                        wanted_disc
                    ),
                    wanted_duration_ms=(
                        duration_ms
                    ),
                )

                # collectionId + Disc + Track bilden innerhalb eines Albums
                # eine eindeutige Position. Ein so bestätigter Treffer ist
                # wesentlich verlässlicher als die allgemeine Suchwertung.
                candidate = MetadataCandidate(
                    source=candidate.source,
                    confidence=100,
                    title=candidate.title,
                    artist=candidate.artist,
                    album_artist=(
                        candidate.album_artist
                    ),
                    album=candidate.album,
                    genre=candidate.genre,
                    year=candidate.year,
                    track=candidate.track,
                    total_tracks=(
                        candidate.total_tracks
                    ),
                    disc=candidate.disc,
                    total_discs=(
                        candidate.total_discs
                    ),
                    isrc=candidate.isrc,
                    label=candidate.label,
                    copyright=(
                        candidate.copyright
                    ),
                    composer=candidate.composer,
                    duration_ms=(
                        candidate.duration_ms
                    ),
                    external_id=(
                        candidate.external_id
                    ),
                    release_id=(
                        candidate.release_id
                    ),
                )
                key = (
                    candidate.external_id
                    or (
                        f"{candidate.release_id}:"
                        f"{candidate.disc}:"
                        f"{candidate.track}"
                    )
                )
                results_by_id[key] = candidate

    return sorted(
        results_by_id.values(),
        key=lambda candidate: (
            -_strict_title_score(
                title,
                alternate_title,
                candidate.title,
            ),
            abs(
                (
                    duration_ms
                    or candidate.duration_ms
                    or 0
                )
                - (
                    candidate.duration_ms
                    or duration_ms
                    or 0
                )
            ),
            candidate.title.casefold(),
        ),
    )


def _strict_title_score(
    title: str,
    alternate_title: str,
    actual_title: str,
) -> int:
    return max(
        _title_score(
            title,
            actual_title,
        ),
        (
            _title_score(
                alternate_title,
                actual_title,
            )
            if alternate_title.strip()
            else -100
        ),
    )


def _search_payload(
    terms: list[str],
    *,
    country: str,
    entity: str,
    limit: int,
) -> dict:
    params = {
        "term": " ".join(terms),
        "country": country.upper(),
        "media": "music",
        "entity": entity,
        "limit": max(
            1,
            min(limit, 200),
        ),
        "lang": "de_de",
        "version": 2,
    }
    request = Request(
        f"{SEARCH_ENDPOINT}?{urlencode(params)}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    return _request_payload(request)


def _request_payload(request: Request) -> dict:
    try:
        return request_json(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except AppleRequestError as error:
        raise AppleMusicProviderError(str(error)) from error


def _unique_countries(
    countries: tuple[str, ...],
) -> tuple[str, ...]:
    result = []

    for country in countries:
        normalized = str(
            country
        ).strip().upper()

        if (
            normalized
            and normalized not in result
        ):
            result.append(normalized)

    return tuple(result)


def _candidate_from_item(
    item: dict,
    *,
    wanted_title: str,
    alternate_title: str,
    wanted_artist: str,
    wanted_album: str,
    wanted_track: str,
    wanted_disc: str,
    wanted_duration_ms: int | None,
) -> MetadataCandidate:
    title = str(
        item.get(
            "trackName",
            "",
        )
    )
    artist = str(
        item.get(
            "artistName",
            "",
        )
    )
    album = str(
        item.get(
            "collectionName",
            "",
        )
    )
    release_date = str(
        item.get(
            "releaseDate",
            "",
        )
    )
    actual_track = _string_number(
        item.get(
            "trackNumber"
        )
    )
    actual_disc = _string_number(
        item.get(
            "discNumber"
        )
    )
    actual_duration_ms = _optional_int(
        item.get(
            "trackTimeMillis"
        )
    )

    score = _match_score(
        wanted_title=wanted_title,
        alternate_title=alternate_title,
        wanted_artist=wanted_artist,
        wanted_album=wanted_album,
        wanted_track=wanted_track,
        wanted_disc=wanted_disc,
        wanted_duration_ms=wanted_duration_ms,
        title=title,
        artist=artist,
        album=album,
        track=actual_track,
        disc=actual_disc,
        duration_ms=actual_duration_ms,
    )

    return MetadataCandidate(
        source="apple_music",
        confidence=score,
        title=title,
        artist=artist,
        album_artist=str(
            item.get(
                "collectionArtistName"
            )
            or artist
        ),
        album=album,
        genre=str(
            item.get(
                "primaryGenreName",
                "",
            )
        ),
        year=_extract_year(
            release_date
        ),
        track=actual_track,
        total_tracks=_string_number(
            item.get(
                "trackCount"
            )
        ),
        disc=actual_disc,
        total_discs=_string_number(
            item.get(
                "discCount"
            )
        ),
        duration_ms=actual_duration_ms,
        external_id=str(
            item.get(
                "trackId",
                "",
            )
        ),
        release_id=str(
            item.get(
                "collectionId",
                "",
            )
        ),
    )


def _match_score(
    *,
    wanted_title: str,
    alternate_title: str,
    wanted_artist: str,
    wanted_album: str,
    wanted_track: str,
    wanted_disc: str,
    wanted_duration_ms: int | None,
    title: str,
    artist: str,
    album: str,
    track: str,
    disc: str,
    duration_ms: int | None,
) -> int:
    title_score = max(
        _title_score(
            wanted_title,
            title,
        ),
        _title_score(
            alternate_title,
            title,
        )
        if alternate_title.strip()
        else -100,
    )
    score = title_score

    score += _field_score(
        wanted_artist,
        artist,
        exact=20,
        contains=11,
    )
    score += _field_score(
        wanted_album,
        album,
        exact=15,
        contains=8,
    )

    wanted_track_number = _optional_int(
        wanted_track
    )
    actual_track_number = _optional_int(
        track
    )

    if (
        wanted_track_number is not None
        and actual_track_number is not None
    ):
        if (
            wanted_track_number
            == actual_track_number
        ):
            score += 35
        else:
            score -= 25

    wanted_disc_number = (
        _optional_int(
            wanted_disc
        )
        or 1
    )
    actual_disc_number = (
        _optional_int(
            disc
        )
        or 1
    )

    if wanted_disc_number == actual_disc_number:
        score += 5
    else:
        score -= 15

    if (
        wanted_duration_ms is not None
        and duration_ms is not None
    ):
        difference = abs(
            wanted_duration_ms
            - duration_ms
        )

        if difference <= 1500:
            score += 25
        elif difference <= 4000:
            score += 15
        elif difference <= 10000:
            score += 5
        elif difference >= 30000:
            score -= 15

    return max(
        0,
        min(
            100,
            score,
        ),
    )


def _title_score(
    wanted: str,
    actual: str,
) -> int:
    wanted_n = _normalize(wanted)
    actual_n = _normalize(actual)

    if not wanted_n:
        return 0

    if wanted_n == actual_n:
        return 70

    wanted_words = set(
        wanted_n.split()
    )
    actual_words = set(
        actual_n.split()
    )

    if (
        not wanted_words
        or not actual_words
    ):
        return 0

    wanted_versions = _canonicalize_versions(
        wanted_words
        & _VERSION_WORDS
    )
    actual_versions = _canonicalize_versions(
        actual_words
        & _VERSION_WORDS
    )

    # Ein ausdrücklich als Remix/Instrumental/etc. bezeichneter lokaler
    # Titel darf nicht auf die normale Albumfassung zurückfallen.
    if wanted_versions:
        if not (
            wanted_versions
            <= actual_versions
        ):
            return -20

        overlap = len(
            wanted_words
            & actual_words
        ) / len(wanted_words)

        if overlap >= 0.75:
            return 65

        return 50

    if actual_versions:
        # Der lokale Titel kann den Versionszusatz noch nicht enthalten.
        # Das bleibt möglich, erhält aber weniger Gewicht als eine
        # vollständige Übereinstimmung.
        core_actual = (
            actual_words
            - actual_versions
        )
        overlap = len(
            wanted_words
            & core_actual
        ) / max(
            1,
            len(wanted_words),
        )

        if overlap >= 0.9:
            return 35

    if (
        wanted_n in actual_n
        or actual_n in wanted_n
    ):
        return 45

    overlap = len(
        wanted_words
        & actual_words
    ) / max(
        len(wanted_words),
        len(actual_words),
    )

    return round(
        35 * overlap
    )



def _canonicalize_versions(
    words: set[str],
) -> set[str]:
    return {
        _VERSION_SYNONYMS.get(
            word,
            word,
        )
        for word in words
    }


def _field_score(
    wanted: str,
    actual: str,
    *,
    exact: int,
    contains: int,
) -> int:
    wanted_n = _normalize(wanted)
    actual_n = _normalize(actual)

    if not wanted_n:
        return 0

    if wanted_n == actual_n:
        return exact

    if (
        wanted_n in actual_n
        or actual_n in wanted_n
    ):
        return contains

    wanted_words = set(
        wanted_n.split()
    )
    actual_words = set(
        actual_n.split()
    )

    if (
        not wanted_words
        or not actual_words
    ):
        return 0

    return round(
        contains
        * len(
            wanted_words
            & actual_words
        )
        / max(
            len(wanted_words),
            len(actual_words),
        )
    )


def _more_specific_title(
    first: str,
    second: str,
) -> str:
    first_words = _normalize(
        first
    ).split()
    second_words = _normalize(
        second
    ).split()

    if len(second_words) > len(first_words):
        return second

    return first


def _normalize(
    value: str,
) -> str:
    value = unicodedata.normalize(
        "NFKD",
        value.casefold(),
    )
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(
            character
        )
    )
    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(
        value.split()
    )


def _extract_year(
    value: str,
) -> str:
    if not value:
        return ""

    try:
        return str(
            datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            ).year
        )
    except ValueError:
        match = re.match(
            r"^(\d{4})",
            value,
        )

        return (
            match.group(1)
            if match
            else ""
        )


def _string_number(
    value: object,
) -> str:
    if value in (
        None,
        "",
    ):
        return ""

    try:
        return str(
            int(value)
        )
    except (
        TypeError,
        ValueError,
    ):
        return str(value)


def _optional_int(
    value: object,
) -> int | None:
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _number_for_sort(
    value: str,
) -> int:
    return (
        _optional_int(value)
        or 9999
    )
