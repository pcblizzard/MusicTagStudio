from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Callable

from mutagen import File as MutagenFile

from ..core.merger import merge_metadata
from ..direct_album_lookup import (
    DirectAlbumLookupError,
    build_album_matching_result,
    lookup_apple_album_by_id,
    lookup_musicbrainz_release_by_id,
)
from ..models.metadata import (
    MergedMetadata,
    MetadataCandidate,
)
from ..models.song import Song
from ..models.source_proposal import SourceProposal
from ..provider_catalog import (
    supported_provider_ids,
)
from ..providers.apple_music import (
    MINIMUM_ALBUM_CONFIDENCE,
    MINIMUM_TRACK_CONFIDENCE,
    AppleMusicProviderError,
    search_album as search_apple_album,
    search_song as search_apple,
    search_song_in_album,
)
from ..providers.musicbrainz import (
    MusicBrainzProviderError,
    MusicBrainzReleaseCandidate,
    search_release as search_mb_release,
    search_song as search_mb,
)
from ..settings import load_settings


@dataclass
class ProposalResult:
    merged: MergedMetadata
    candidates: list[MetadataCandidate]
    warnings: list[str]
    sources: dict[str, SourceProposal]

    def candidate_for(
        self,
        source: str,
    ) -> MetadataCandidate | None:
        proposal = self.sources.get(
            source
        )

        return (
            proposal.candidate
            if proposal is not None
            else None
        )


ProgressCallback = Callable[
    [int, int, str],
    None,
]
CancelCallback = Callable[
    [],
    bool,
]


def build_proposal(
    song: Song,
) -> ProposalResult:
    settings = load_settings()
    candidates: list[
        MetadataCandidate
    ] = []
    warnings: list[str] = []

    provider_order = _provider_order(
        settings.selected_provider,
        settings.enrich_missing_fields,
    )

    filename_title = _title_from_filename(
        song.path
    )
    duration_ms = _local_duration_ms(
        song.path
    )

    for provider_id in provider_order:
        if provider_id == "apple_music":
            try:
                results = search_apple(
                    song.title,
                    song.artist,
                    song.album,
                    alternate_title=filename_title,
                    wanted_track=song.track,
                    wanted_disc=song.disc,
                    duration_ms=duration_ms,
                    country=(
                        settings.apple_country
                    ),
                    limit=50,
                )

                acceptable = next(
                    (
                        result
                        for result in results
                        if (
                            result.confidence
                            >= MINIMUM_TRACK_CONFIDENCE
                        )
                    ),
                    None,
                )

                if acceptable is not None:
                    candidates.append(
                        acceptable
                    )
                elif results:
                    warnings.append(
                        "Apple Music lieferte keinen ausreichend "
                        "sicheren Treffer. Der beste unsichere "
                        f"Treffer war „{results[0].title}“ "
                        f"({results[0].confidence} %)."
                    )
            except AppleMusicProviderError as error:
                warnings.append(
                    str(error)
                )

        elif provider_id == "musicbrainz":
            try:
                results = search_mb(
                    song.title,
                    song.artist,
                    song.album,
                    limit=10,
                )

                if results:
                    candidates.append(
                        results[0]
                    )
            except MusicBrainzProviderError as error:
                warnings.append(
                    str(error)
                )

    return _proposal_result(
        song,
        candidates,
        warnings,
        primary_source=(
            settings.selected_provider
        ),
        feature_handling=(
            settings.feature_handling
        ),
    )


def build_batch_proposals(
    songs: list[Song],
    *,
    progress_callback: (
        ProgressCallback | None
    ) = None,
    cancel_callback: (
        CancelCallback | None
    ) = None,
) -> list[ProposalResult]:
    """
    Erstellt Batch-Vorschläge albumweise.

    Apple Music wird nicht mehr für jeden Titel unabhängig durchsucht.
    Stattdessen wird zuerst das Album gesucht, anschließend die vollständige
    offizielle Trackliste geladen und global den lokalen Dateien zugeordnet.
    Dadurch kann Track 7 nicht versehentlich Track 1 oder Track 11 erhalten.
    """
    settings = load_settings()
    provider_order = _provider_order(
        settings.selected_provider,
        settings.enrich_missing_fields,
    )
    candidates_by_index: list[
        list[MetadataCandidate]
    ] = [
        []
        for _ in songs
    ]
    warnings_by_index: list[
        list[str]
    ] = [
        []
        for _ in songs
    ]

    apple_resolved_indexes: set[int] = set()
    musicbrainz_resolved_indexes: set[int] = set()

    if "apple_music" in provider_order:
        apple_resolved_indexes = (
            _add_album_aware_apple_candidates(
                songs,
                candidates_by_index,
                warnings_by_index,
                country=settings.apple_country,
            )
        )

    if "musicbrainz" in provider_order:
        musicbrainz_resolved_indexes = (
            _add_album_aware_musicbrainz_candidates(
                songs,
                candidates_by_index,
                warnings_by_index,
            )
        )

    total = len(songs)

    for index, song in enumerate(
        songs
    ):
        if (
            cancel_callback is not None
            and cancel_callback()
        ):
            break

        if progress_callback is not None:
            progress_callback(
                index,
                total,
                song.title,
            )

        if (
            "apple_music" in provider_order
            and index not in apple_resolved_indexes
            and not any(
                candidate.source
                == "apple_music"
                for candidate
                in candidates_by_index[
                    index
                ]
            )
        ):
            _add_safe_single_apple_candidate(
                song,
                candidates_by_index[
                    index
                ],
                warnings_by_index[
                    index
                ],
                country=(
                    settings.apple_country
                ),
            )

        if (
            "musicbrainz" in provider_order
            and index
            not in musicbrainz_resolved_indexes
        ):
            try:
                results = search_mb(
                    song.title,
                    song.artist,
                    song.album,
                    limit=10,
                )

                if results:
                    candidates_by_index[
                        index
                    ].append(
                        results[0]
                    )
            except MusicBrainzProviderError as error:
                warnings_by_index[
                    index
                ].append(
                    str(error)
                )

    completed_count = min(
        total,
        next(
            (
                index
                for index in range(total)
                if (
                    not candidates_by_index[index]
                    and not warnings_by_index[index]
                    and cancel_callback is not None
                    and cancel_callback()
                )
            ),
            total,
        ),
    )

    if progress_callback is not None:
        progress_callback(
            completed_count,
            total,
            "Abgeschlossen",
        )

    return [
        _proposal_result(
            song,
            candidates_by_index[index],
            warnings_by_index[index],
            primary_source=(
                settings.selected_provider
            ),
            feature_handling=(
                settings.feature_handling
            ),
        )
        for index, song in enumerate(
            songs
        )
    ]


def _add_album_aware_apple_candidates(
    songs: list[Song],
    candidates_by_index: list[
        list[MetadataCandidate]
    ],
    warnings_by_index: list[
        list[str]
    ],
    *,
    country: str,
) -> set[int]:
    """
    Verarbeitet Apple Music albumweise.

    Sobald ein Album sicher erkannt wurde, gelten alle Titel dieser Gruppe als
    albumgebunden behandelt. Fehlende Tracks werden nur noch streng innerhalb
    derselben collectionId, Disc und Tracknummer gesucht. Eine allgemeine
    Song-Suche darf dann keinen ähnlich klingenden Titel aus einem anderen
    Album oder von einer anderen Position einsetzen.
    """
    handled_indexes: set[int] = set()

    for indexes in _album_groups(
        songs
    ).values():
        group_songs = [
            songs[index]
            for index in indexes
        ]
        (
            album_name,
            album_artist,
            wanted_year,
            expected_track_count,
        ) = _album_identity(
            group_songs
        )

        if not album_name:
            continue

        store_order = [
            country.upper(),
        ]

        if "US" not in store_order:
            store_order.append("US")

        album_candidates = []

        for store in store_order:
            try:
                found = search_apple_album(
                    album_name,
                    album_artist,
                    expected_track_count=(
                        expected_track_count
                    ),
                    wanted_year=wanted_year,
                    country=store,
                    limit=30,
                )
            except AppleMusicProviderError as error:
                _append_group_warning(
                    warnings_by_index,
                    indexes,
                    str(error),
                )
                continue

            album_candidates.extend(
                candidate
                for candidate in found[:5]
                if (
                    candidate.confidence
                    >= MINIMUM_ALBUM_CONFIDENCE
                )
            )

        album_candidates = (
            _deduplicate_apple_album_candidates(
                album_candidates
            )
        )

        if not album_candidates:
            # Kein Album sicher erkannt. Erst dann ist der allgemeine,
            # streng bewertete Einzeltitel-Fallback zulässig.
            continue

        options = []

        for candidate in album_candidates:
            try:
                album_result = (
                    lookup_apple_album_by_id(
                        candidate.collection_id,
                        country=(
                            candidate.country
                        ),
                    )
                )
            except DirectAlbumLookupError:
                continue

            matching = (
                build_album_matching_result(
                    group_songs,
                    album_result,
                )
            )
            options.append(
                (
                    _matching_rank(
                        matching,
                        album_result,
                        expected_track_count,
                        candidate.confidence,
                        preferred_store=(
                            candidate.country
                            == country.upper()
                        ),
                    ),
                    candidate,
                    album_result,
                    matching,
                )
            )

        # Das Album ist bereits durch die offizielle Albumsuche bekannt.
        # Selbst wenn die alte iTunes-Lookup-Trackliste unvollständig ist,
        # darf deshalb kein beliebiger Song aus einer allgemeinen Suche
        # übernommen werden.
        handled_indexes.update(indexes)

        if options:
            (
                _best_rank,
                selected_candidate,
                album_result,
                matching,
            ) = max(
                options,
                key=lambda item: item[0],
            )
            selected_collection_id = (
                selected_candidate.collection_id
            )
            selected_store = (
                selected_candidate.country
            )
            matched_local_indexes = set()

            for match in matching.matches:
                if (
                    match.confidence
                    == "Mehrdeutig"
                    and match.score < 80
                ):
                    continue

                global_index = indexes[
                    match.local_index
                ]
                candidates_by_index[
                    global_index
                ].append(
                    replace(
                        match.track.as_candidate(
                            "apple_music"
                        ),
                        confidence=min(
                            100,
                            max(
                                0,
                                match.score,
                            ),
                        ),
                        release_id=(
                            selected_collection_id
                        ),
                    )
                )
                matched_local_indexes.add(
                    match.local_index
                )

            missing_local_indexes = [
                local_index
                for local_index in range(
                    len(group_songs)
                )
                if local_index
                not in matched_local_indexes
            ]
        else:
            # Die Albumsuche kennt das Album, aber Lookup lieferte in keinem
            # Store eine verwendbare Trackliste. Wir nutzen dennoch die beste
            # sichere collectionId für eine streng albumgebundene Titelsuche.
            selected_candidate = max(
                album_candidates,
                key=lambda item: (
                    item.confidence,
                    item.country
                    == country.upper(),
                ),
            )
            selected_collection_id = (
                selected_candidate.collection_id
            )
            selected_store = (
                selected_candidate.country
            )
            missing_local_indexes = list(
                range(
                    len(group_songs)
                )
            )

        recovery_countries = tuple(
            dict.fromkeys(
                (
                    selected_store,
                    country.upper(),
                    "US",
                )
            )
        )

        for local_index in (
            missing_local_indexes
        ):
            song = group_songs[
                local_index
            ]

            try:
                recovered = (
                    search_song_in_album(
                        song.title,
                        (
                            song.album_artist
                            or song.artist
                        ),
                        song.album,
                        collection_id=(
                            selected_collection_id
                        ),
                        alternate_title=(
                            _title_from_filename(
                                song.path
                            )
                        ),
                        wanted_track=(
                            song.track
                        ),
                        wanted_disc=(
                            song.disc
                        ),
                        duration_ms=(
                            _local_duration_ms(
                                song.path
                            )
                        ),
                        countries=(
                            recovery_countries
                        ),
                        limit=200,
                    )
                )
            except AppleMusicProviderError as error:
                warnings_by_index[
                    indexes[local_index]
                ].append(
                    str(error)
                )
                continue

            if recovered:
                candidates_by_index[
                    indexes[local_index]
                ].append(
                    recovered[0]
                )
            else:
                warnings_by_index[
                    indexes[local_index]
                ].append(
                    (
                        "Apple Music: Das Album wurde sicher erkannt, "
                        f"aber Disc {song.disc or '1'} / "
                        f"Track {song.track or '?'} konnte innerhalb "
                        "dieser collectionId nicht über die offiziellen "
                        "Search-/Lookup-Schnittstellen gefunden werden."
                    )
                )

        if selected_store != country.upper():
            _append_group_warning(
                warnings_by_index,
                indexes,
                (
                    "Für die vollständigste offizielle "
                    "Apple-Zuordnung wurde der "
                    f"{selected_store}-Store verwendet."
                ),
            )

    return handled_indexes


def _deduplicate_apple_album_candidates(
    candidates,
):
    result = []
    seen = set()

    for candidate in candidates:
        key = (
            candidate.collection_id,
            candidate.country,
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(candidate)

    return result

def _add_album_aware_musicbrainz_candidates(
    songs: list[Song],
    candidates_by_index: list[
        list[MetadataCandidate]
    ],
    warnings_by_index: list[
        list[str]
    ],
) -> set[int]:
    resolved_indexes: set[int] = set()

    for indexes in _album_groups(
        songs
    ).values():
        group_songs = [
            songs[index]
            for index in indexes
        ]
        album_name, album_artist, wanted_year, expected_track_count = (
            _album_identity(
                group_songs
            )
        )

        if not album_name:
            continue

        try:
            release_candidates = (
                search_mb_release(
                    album_name,
                    album_artist,
                    expected_track_count=(
                        expected_track_count
                    ),
                    wanted_year=wanted_year,
                    limit=25,
                )
            )
        except MusicBrainzProviderError as error:
            _append_group_warning(
                warnings_by_index,
                indexes,
                str(error),
            )
            continue

        options = []

        for candidate in release_candidates[:3]:
            if candidate.confidence < 65:
                continue

            try:
                album_result = (
                    lookup_musicbrainz_release_by_id(
                        candidate.release_id
                    )
                )
            except DirectAlbumLookupError:
                continue

            matching = (
                build_album_matching_result(
                    group_songs,
                    album_result,
                )
            )
            options.append(
                (
                    _matching_rank(
                        matching,
                        album_result,
                        expected_track_count,
                        candidate.confidence,
                        preferred_store=True,
                    ),
                    candidate,
                    matching,
                )
            )

        if not options:
            continue

        best_rank, candidate, matching = max(
            options,
            key=lambda item: item[0],
        )

        if best_rank[0] == 0:
            continue

        matched_local_indexes: set[int] = set()

        for match in matching.matches:
            if (
                match.confidence
                == "Mehrdeutig"
                and match.score < 70
            ):
                continue

            global_index = indexes[
                match.local_index
            ]
            candidates_by_index[
                global_index
            ].append(
                replace(
                    match.track.as_candidate(
                        "musicbrainz"
                    ),
                    confidence=min(
                        100,
                        max(0, match.score),
                    ),
                    release_id=(
                        candidate.release_id
                    ),
                )
            )
            matched_local_indexes.add(
                match.local_index
            )
            resolved_indexes.add(
                global_index
            )

        # Nur wirklich zugeordnete Dateien gelten als erledigt.
        # Unklare oder fehlende Album-Matches dürfen anschließend noch
        # über die titelweise MusicBrainz-Suche ergänzt werden.
        unresolved_local_indexes = [
            local_index
            for local_index in range(
                len(group_songs)
            )
            if local_index
            not in matched_local_indexes
        ]

        for local_index in (
            unresolved_local_indexes
        ):
            global_index = indexes[
                local_index
            ]
            warnings_by_index[
                global_index
            ].append(
                "MusicBrainz: Der Titel konnte der ausgewählten "
                "Release-Trackliste nicht sicher zugeordnet werden. "
                "Es wird zusätzlich eine titelweise Suche versucht."
            )

    return resolved_indexes


def _matching_rank(
    matching,
    album_result,
    expected_track_count: int,
    source_confidence: int,
    *,
    preferred_store: bool,
) -> tuple[int, ...]:
    accepted_matches = [
        match
        for match in matching.matches
        if not (
            match.confidence == "Mehrdeutig"
            and match.score < 70
        )
    ]
    exact_tracklist = int(
        len(album_result.tracks)
        == expected_track_count
    )

    return (
        len(accepted_matches),
        -len(
            matching.unmatched_local_indexes
        ),
        exact_tracklist,
        sum(
            match.score
            for match in accepted_matches
        ),
        source_confidence,
        int(preferred_store),
    )


def _album_groups(
    songs: list[Song],
) -> dict[str, list[int]]:
    groups: dict[
        str,
        list[int],
    ] = defaultdict(list)

    for index, song in enumerate(songs):
        directory = str(
            Path(song.path).parent.resolve()
        ).casefold()
        groups[directory].append(index)

    return groups


def _album_identity(
    songs: list[Song],
) -> tuple[str, str, str, int]:
    album_name = _most_common_text(
        song.album
        for song in songs
    )
    album_artist = _most_common_text(
        (
            song.album_artist
            or song.artist
        )
        for song in songs
    )
    wanted_year = _most_common_text(
        song.year
        for song in songs
    )
    expected_track_count = (
        _most_common_positive_int(
            song.total_tracks
            for song in songs
        )
        or len(songs)
    )

    return (
        album_name,
        album_artist,
        wanted_year,
        expected_track_count,
    )


def _warn_unmatched_album_tracks(
    matching,
    indexes: list[int],
    warnings_by_index: list[
        list[str]
    ],
    *,
    source_label: str,
) -> None:
    for local_index in (
        matching.unmatched_local_indexes
    ):
        global_index = indexes[
            local_index
        ]
        warnings_by_index[
            global_index
        ].append(
            f"{source_label}: Dieser Titel konnte "
            "der vollständigen Albumtrackliste "
            "nicht sicher zugeordnet werden."
        )

def _add_safe_single_apple_candidate(
    song: Song,
    candidates: list[
        MetadataCandidate
    ],
    warnings: list[str],
    *,
    country: str,
) -> None:
    stores = [
        country.upper(),
    ]

    if "US" not in stores:
        stores.append("US")

    all_results: list[
        MetadataCandidate
    ] = []

    for store in stores:
        try:
            all_results.extend(
                search_apple(
                    song.title,
                    song.artist,
                    song.album,
                    alternate_title=(
                        _title_from_filename(
                            song.path
                        )
                    ),
                    wanted_track=(
                        song.track
                    ),
                    wanted_disc=(
                        song.disc
                    ),
                    duration_ms=(
                        _local_duration_ms(
                            song.path
                        )
                    ),
                    country=store,
                    limit=100,
                )
            )
        except AppleMusicProviderError as error:
            warnings.append(
                str(error)
            )

    deduplicated = {}

    for result in all_results:
        key = (
            result.external_id
            or (
                f"{result.release_id}:"
                f"{result.disc}:"
                f"{result.track}:"
                f"{result.title}"
            )
        )
        previous = deduplicated.get(
            key
        )

        if (
            previous is None
            or result.confidence
            > previous.confidence
        ):
            deduplicated[key] = result

    results = sorted(
        deduplicated.values(),
        key=lambda result:
        -result.confidence,
    )
    acceptable = next(
        (
            result
            for result in results
            if (
                result.confidence
                >= MINIMUM_TRACK_CONFIDENCE
            )
        ),
        None,
    )

    if acceptable is not None:
        candidates.append(
            acceptable
        )
    elif results:
        warnings.append(
            "Kein ausreichend sicherer Apple-Treffer. "
            f"„{results[0].title}“ wurde wegen nur "
            f"{results[0].confidence} % Sicherheit "
            "nicht übernommen."
        )

def _proposal_result(
    song: Song,
    candidates: list[
        MetadataCandidate
    ],
    warnings: list[str],
    *,
    primary_source: str,
    feature_handling: str,
) -> ProposalResult:
    by_source = {
        candidate.source: candidate
        for candidate in candidates
    }
    warning_map: dict[
        str,
        list[str],
    ] = {
        source: []
        for source
        in supported_provider_ids()
    }

    for warning in warnings:
        lowered = warning.casefold()

        if "musicbrainz" in lowered:
            warning_map.setdefault(
                "musicbrainz",
                [],
            ).append(warning)
        elif (
            "apple" in lowered
            or "store" in lowered
            or "collectionid" in lowered
        ):
            warning_map.setdefault(
                "apple_music",
                [],
            ).append(warning)

    sources: dict[
        str,
        SourceProposal,
    ] = {}

    for source in supported_provider_ids():
        candidate = by_source.get(
            source
        )
        source_warnings = tuple(
            warning_map.get(
                source,
                (),
            )
        )

        if candidate is not None:
            status = "matched"
        elif source_warnings:
            status = (
                "error"
                if any(
                    word in warning.casefold()
                    for warning
                    in source_warnings
                    for word in (
                        "fehler",
                        "keine verbindung",
                        "konnte nicht geladen",
                    )
                )
                else "not_found"
            )
        else:
            status = "not_found"

        sources[source] = SourceProposal(
            source=source,
            status=status,
            candidate=candidate,
            warnings=source_warnings,
        )

    return ProposalResult(
        merged=merge_metadata(
            song,
            candidates,
            feature_handling=(
                feature_handling
            ),
            primary_source=(
                primary_source
            ),
        ),
        candidates=candidates,
        warnings=warnings,
        sources=sources,
    )

def _provider_order(
    selected_provider: str,
    enrich_missing_fields: bool,
) -> list[str]:
    """
    Liefert alle unterstützten Quellen.

    Die bevorzugte Quelle steht nur zuerst und bestimmt die Vorauswahl in der
    Oberfläche. Sie unterdrückt keine andere Quelle. Dadurch zeigt der
    Vergleich immer den tatsächlichen Apple-Music- und MusicBrainz-Wert
    unabhängig voneinander an.
    """
    supported = list(
        supported_provider_ids()
    )

    if selected_provider in supported:
        supported.remove(
            selected_provider
        )

        return [
            selected_provider,
            *supported,
        ]

    return supported

def _append_group_warning(
    warnings_by_index: list[
        list[str]
    ],
    indexes: list[int],
    warning: str,
) -> None:
    for index in indexes:
        warnings_by_index[
            index
        ].append(warning)


def _most_common_text(
    values,
) -> str:
    cleaned = [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]

    if not cleaned:
        return ""

    return Counter(
        cleaned
    ).most_common(1)[0][0]


def _most_common_positive_int(
    values,
) -> int | None:
    numbers = []

    for value in values:
        try:
            number = int(value)
        except (
            TypeError,
            ValueError,
        ):
            continue

        if number > 0:
            numbers.append(number)

    if not numbers:
        return None

    return Counter(
        numbers
    ).most_common(1)[0][0]


def _title_from_filename(
    filepath: str,
) -> str:
    if not filepath:
        return ""

    stem = Path(filepath).stem
    stem = re.sub(
        r"^\s*(?:\d{1,2}[-_.])?\d{1,3}\s*[.)_-]\s*",
        "",
        stem,
    )

    if " - " in stem:
        stem = stem.split(
            " - ",
            1,
        )[1]

    return stem.strip()


@lru_cache(maxsize=4096)
def _local_duration_ms(
    filepath: str,
) -> int | None:
    path = Path(filepath)

    if not path.is_file():
        return None

    try:
        audio = MutagenFile(path)
    except Exception:
        return None

    info = getattr(
        audio,
        "info",
        None,
    )
    length = getattr(
        info,
        "length",
        None,
    )

    if length is None:
        return None

    try:
        return round(
            float(length) * 1000
        )
    except (
        TypeError,
        ValueError,
    ):
        return None
