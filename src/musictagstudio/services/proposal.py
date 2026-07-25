from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from ..core.merger import merge_metadata
from ..diagnostics import get_diagnostic_logger
from ..local_track import local_duration_ms, title_from_filename
from ..direct_album_lookup import (
    DirectAlbumLookupError,
    apple_collection_id_from_musicbrainz_release,
    build_album_matching_result,
    find_apple_track_in_album,
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
    AppleAlbumCandidate,
    AppleMusicProviderError,
    search_album as search_apple_album,
    search_albums_via_web,
    search_song as search_apple,
    search_song_in_album,
)
from ..providers.musicbrainz import (
    MusicBrainzProviderError,
    search_release as search_mb_release,
    search_song as search_mb,
)
from ..providers import deezer
from ..providers.deezer import DeezerProviderError
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
        proposal = self.sources.get(source)

        return proposal.candidate if proposal is not None else None


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
    candidates: list[MetadataCandidate] = []
    warnings: list[str] = []

    provider_order = _provider_order(
        settings.selected_provider,
        settings.enrich_missing_fields,
    )

    filename_title = _title_from_filename(song.path)
    duration_ms = _local_duration_ms(song.path)

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
                    country=(settings.apple_country),
                    limit=50,
                )

                acceptable = next(
                    (
                        result
                        for result in results
                        if (result.confidence >= MINIMUM_TRACK_CONFIDENCE)
                    ),
                    None,
                )

                if acceptable is not None:
                    candidates.append(acceptable)
                elif results:
                    warnings.append(
                        "Apple Music lieferte keinen ausreichend "
                        "sicheren Treffer. Der beste unsichere "
                        f"Treffer war „{results[0].title}“ "
                        f"({results[0].confidence} %)."
                    )
            except AppleMusicProviderError as error:
                warnings.append(str(error))

        elif provider_id == "musicbrainz":
            try:
                results = search_mb(
                    song.title,
                    song.artist,
                    song.album,
                    limit=10,
                )

                if results:
                    candidates.append(results[0])
            except MusicBrainzProviderError as error:
                warnings.append(str(error))

        elif provider_id == "deezer":
            deezer_results = deezer.search_song(
                song.title,
                song.artist,
                song.album,
                limit=10,
            )
            acceptable = next(
                (
                    result
                    for result in deezer_results
                    if result.confidence >= MINIMUM_TRACK_CONFIDENCE
                ),
                None,
            )

            if acceptable is not None:
                candidates.append(acceptable)

    return _proposal_result(
        song,
        candidates,
        warnings,
        primary_source=(settings.selected_provider),
        feature_handling=(settings.feature_handling),
    )


def build_batch_proposals(
    songs: list[Song],
    *,
    progress_callback: (ProgressCallback | None) = None,
    cancel_callback: (CancelCallback | None) = None,
) -> list[ProposalResult]:
    """
    Erstellt Batch-Vorschläge albumweise.

    Apple Music wird nicht mehr für jeden Titel unabhängig durchsucht.
    Stattdessen wird zuerst das Album gesucht, anschließend die vollständige
    offizielle Trackliste geladen und global den lokalen Dateien zugeordnet.
    Dadurch kann Track 7 nicht versehentlich Track 1 oder Track 11 erhalten.
    """
    logger = get_diagnostic_logger("proposal")
    logger.info(
        "BATCH START | Titel=%d",
        len(songs),
    )

    for index, song in enumerate(songs):
        logger.info(
            "LOKALER TITEL | Index=%d | Datei=%s | Titel=%r | "
            "Künstler=%r | Albumkünstler=%r | Album=%r | "
            "Track=%r/%r | Disc=%r/%r | Jahr=%r",
            index,
            song.path,
            song.title,
            song.artist,
            song.album_artist,
            song.album,
            song.track,
            song.total_tracks,
            song.disc,
            song.total_discs,
            song.year,
        )

    settings = load_settings()
    logger.info(
        "BATCH EINSTELLUNGEN | Bevorzugte Quelle=%s | Apple-Store=%s | Ergänzen=%s",
        settings.selected_provider,
        settings.apple_country,
        settings.enrich_missing_fields,
    )
    provider_order = _provider_order(
        settings.selected_provider,
        settings.enrich_missing_fields,
    )
    logger.info(
        "BATCH PROVIDER | Reihenfolge=%r",
        provider_order,
    )
    candidates_by_index: list[list[MetadataCandidate]] = [[] for _ in songs]
    warnings_by_index: list[list[str]] = [[] for _ in songs]

    apple_resolved_indexes: set[int] = set()
    musicbrainz_resolved_indexes: set[int] = set()
    deezer_resolved_indexes: set[int] = set()

    # Der Apple- und der MusicBrainz-Albumpfad nutzen getrennte
    # Rate-Limit-Sperren und können deshalb gleichzeitig laufen. Jeder Pfad
    # schreibt in eigene Puffer, die anschließend deterministisch (Apple vor
    # MusicBrainz) zusammengeführt werden.
    apple_candidates: list[list[MetadataCandidate]] = [[] for _ in songs]
    apple_warnings: list[list[str]] = [[] for _ in songs]
    mb_candidates: list[list[MetadataCandidate]] = [[] for _ in songs]
    mb_warnings: list[list[str]] = [[] for _ in songs]
    deezer_candidates: list[list[MetadataCandidate]] = [[] for _ in songs]
    deezer_warnings: list[list[str]] = [[] for _ in songs]

    def _run_apple() -> set[int]:
        return _add_album_aware_apple_candidates(
            songs,
            apple_candidates,
            apple_warnings,
            country=settings.apple_country,
        )

    def _run_musicbrainz() -> set[int]:
        return _add_album_aware_musicbrainz_candidates(
            songs,
            mb_candidates,
            mb_warnings,
        )

    def _run_deezer() -> set[int]:
        return _add_album_aware_deezer_candidates(
            songs,
            deezer_candidates,
            deezer_warnings,
        )

    with ThreadPoolExecutor(max_workers=3) as executor:
        apple_future = (
            executor.submit(_run_apple)
            if "apple_music" in provider_order
            else None
        )
        mb_future = (
            executor.submit(_run_musicbrainz)
            if "musicbrainz" in provider_order
            else None
        )
        deezer_future = (
            executor.submit(_run_deezer)
            if "deezer" in provider_order
            else None
        )

        if apple_future is not None:
            apple_resolved_indexes = apple_future.result()
        if mb_future is not None:
            musicbrainz_resolved_indexes = mb_future.result()
        if deezer_future is not None:
            deezer_resolved_indexes = deezer_future.result()

    for index in range(len(songs)):
        candidates_by_index[index].extend(apple_candidates[index])
        candidates_by_index[index].extend(mb_candidates[index])
        candidates_by_index[index].extend(deezer_candidates[index])
        warnings_by_index[index].extend(apple_warnings[index])
        warnings_by_index[index].extend(mb_warnings[index])
        warnings_by_index[index].extend(deezer_warnings[index])

    logger.info(
        "APPLE ALBUMPFAD BEENDET | Behandelte Indizes=%r",
        sorted(apple_resolved_indexes),
    )

    total = len(songs)

    for index, song in enumerate(songs):
        if cancel_callback is not None and cancel_callback():
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
                candidate.source == "apple_music"
                for candidate in candidates_by_index[index]
            )
        ):
            logger.warning(
                "APPLE EINZELFALLBACK | Index=%d | Titel=%r | Album=%r | Track=%r",
                index,
                song.title,
                song.album,
                song.track,
            )
            _add_safe_single_apple_candidate(
                song,
                candidates_by_index[index],
                warnings_by_index[index],
                country=(settings.apple_country),
            )

        if (
            "musicbrainz" in provider_order
            and index not in musicbrainz_resolved_indexes
        ):
            try:
                results = search_mb(
                    song.title,
                    song.artist,
                    song.album,
                    limit=10,
                )

                if results:
                    candidates_by_index[index].append(results[0])
            except MusicBrainzProviderError as error:
                warnings_by_index[index].append(str(error))

        if (
            "deezer" in provider_order
            and index not in deezer_resolved_indexes
            and not any(
                candidate.source == "deezer"
                for candidate in candidates_by_index[index]
            )
        ):
            deezer_results = deezer.search_song(
                song.title,
                song.artist,
                song.album,
                limit=10,
            )

            if deezer_results:
                candidates_by_index[index].append(deezer_results[0])

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

    for index, candidates in enumerate(candidates_by_index):
        logger.info(
            "BATCH ERGEBNIS | Index=%d | Quellen=%r | Warnungen=%r",
            index,
            [
                (
                    candidate.source,
                    candidate.title,
                    candidate.track,
                    candidate.confidence,
                )
                for candidate in candidates
            ],
            warnings_by_index[index],
        )

    logger.info(
        "BATCH ENDE | Titel=%d",
        len(songs),
    )

    return [
        _proposal_result(
            song,
            candidates_by_index[index],
            warnings_by_index[index],
            primary_source=(settings.selected_provider),
            feature_handling=(settings.feature_handling),
        )
        for index, song in enumerate(songs)
    ]


def _add_album_aware_apple_candidates(
    songs: list[Song],
    candidates_by_index: list[list[MetadataCandidate]],
    warnings_by_index: list[list[str]],
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
    logger = get_diagnostic_logger("proposal")
    handled_indexes: set[int] = set()
    groups = _album_groups(songs)
    logger.info(
        "APPLE ALBUMPFAD START | Gruppen=%d | Gruppenschlüssel=%r",
        len(groups),
        list(groups.keys()),
    )

    for group_key, indexes in groups.items():
        logger.info(
            "APPLE GRUPPE | Schlüssel=%r | Indizes=%r",
            group_key,
            indexes,
        )
        group_songs = [songs[index] for index in indexes]
        (
            album_name,
            album_artist,
            wanted_year,
            expected_track_count,
        ) = _album_identity(group_songs)

        logger.info(
            "APPLE ALBUMIDENTITÄT | Schlüssel=%r | Album=%r | "
            "Albumkünstler=%r | Jahr=%r | Erwartete Tracks=%r",
            group_key,
            album_name,
            album_artist,
            wanted_year,
            expected_track_count,
        )

        if not album_name:
            logger.warning(
                "APPLE GRUPPE ÜBERSPRUNGEN | Schlüssel=%r | Grund=kein Albumname",
                group_key,
            )
            continue

        store_order = [
            country.upper(),
        ]

        if "US" not in store_order:
            store_order.append("US")

        album_candidates = []

        for store in store_order:
            logger.info(
                "APPLE ALBUMSUCHE AUFRUF | Schlüssel=%r | Store=%s",
                group_key,
                store,
            )

            found = []
            search_error = None

            for album_variant in _apple_album_title_variants(album_name):
                logger.info(
                    "APPLE ALBUMSUCHE VARIANTE | Schlüssel=%r | Store=%s | Album=%r",
                    group_key,
                    store,
                    album_variant,
                )

                try:
                    variant_results = search_apple_album(
                        album_variant,
                        album_artist,
                        expected_track_count=(expected_track_count),
                        wanted_year=(wanted_year),
                        country=store,
                        limit=30,
                    )
                except AppleMusicProviderError as error:
                    search_error = error
                    logger.warning(
                        "APPLE ALBUMSUCHE VARIANTE FEHLER | "
                        "Schlüssel=%r | Store=%s | Album=%r | %s",
                        group_key,
                        store,
                        album_variant,
                        error,
                    )
                    continue

                found.extend(variant_results)

                if any(
                    candidate.confidence >= MINIMUM_ALBUM_CONFIDENCE
                    for candidate in variant_results
                ):
                    break

            found = _deduplicate_apple_album_candidates(found)

            if not found and search_error is not None:
                _append_group_warning(
                    warnings_by_index,
                    indexes,
                    str(search_error),
                )

            logger.info(
                "APPLE ALBUMSUCHE RESULTAT | Schlüssel=%r | Store=%s | "
                "Gefunden=%r | Mindestscore=%s",
                group_key,
                store,
                [
                    (
                        candidate.collection_id,
                        candidate.album,
                        candidate.artist,
                        candidate.track_count,
                        candidate.year,
                        candidate.confidence,
                    )
                    for candidate in found[:10]
                ],
                MINIMUM_ALBUM_CONFIDENCE,
            )
            accepted = [
                candidate
                for candidate in found[:5]
                if (candidate.confidence >= MINIMUM_ALBUM_CONFIDENCE)
            ]
            logger.info(
                "APPLE ALBUMSUCHE AKZEPTIERT | Schlüssel=%r | Store=%s | Kandidaten=%r",
                group_key,
                store,
                [
                    (
                        candidate.collection_id,
                        candidate.confidence,
                    )
                    for candidate in accepted
                ],
            )
            album_candidates.extend(accepted)

        album_candidates = _deduplicate_apple_album_candidates(album_candidates)

        if not album_candidates:
            logger.warning(
                "APPLE ALBUMSUCHE OHNE TREFFER | Schlüssel=%r | "
                "Collection-ID wird über weitere Quellen gesucht",
                group_key,
            )

        # 1. Öffentliche Apple-Music-Websuche: deckt den vollen Katalog ab
        #    und findet Alben, die die iTunes-Such-API nicht indexiert.
        if not album_candidates:
            web_candidate = _apple_candidate_via_web_search(
                album_name=album_name,
                album_artist=album_artist,
                wanted_year=wanted_year,
                expected_track_count=expected_track_count,
                store=store_order[0],
            )

            if web_candidate is not None:
                album_candidates = [web_candidate]
                logger.info(
                    "APPLE COLLECTION-ID ÜBER WEBSUCHE | "
                    "Schlüssel=%r | Collection-ID=%s | Store=%s | "
                    "Album=%r | Tracks=%s | Score=%s",
                    group_key,
                    web_candidate.collection_id,
                    web_candidate.country,
                    web_candidate.album,
                    web_candidate.track_count,
                    web_candidate.confidence,
                )

        # 2. Rekonstruktion aus Einzeltitel-Konsens.
        if not album_candidates:
            recovered_candidate = _recover_apple_album_candidate_from_songs(
                group_songs,
                album_name=album_name,
                album_artist=album_artist,
                wanted_year=wanted_year,
                expected_track_count=expected_track_count,
                countries=tuple(store_order),
            )

            if recovered_candidate is not None:
                album_candidates = [recovered_candidate]
                logger.info(
                    "APPLE COLLECTION-ID REKONSTRUIERT | "
                    "Schlüssel=%r | Collection-ID=%s | Store=%s | "
                    "Album=%r | Tracks=%s | Score=%s",
                    group_key,
                    recovered_candidate.collection_id,
                    recovered_candidate.country,
                    recovered_candidate.album,
                    recovered_candidate.track_count,
                    recovered_candidate.confidence,
                )

        # 3. Apple-Verweis über eine MusicBrainz-Release-Relation.
        if not album_candidates:
            bridged_candidate = _apple_candidate_via_musicbrainz(
                album_name=album_name,
                album_artist=album_artist,
                wanted_year=wanted_year,
                expected_track_count=expected_track_count,
                store=store_order[0],
            )

            if bridged_candidate is not None:
                album_candidates = [bridged_candidate]
                logger.info(
                    "APPLE COLLECTION-ID ÜBER MUSICBRAINZ | "
                    "Schlüssel=%r | Collection-ID=%s | Store=%s",
                    group_key,
                    bridged_candidate.collection_id,
                    bridged_candidate.country,
                )

        if not album_candidates:
            logger.warning(
                "APPLE ALBUMPFAD ABBRUCH | Schlüssel=%r | "
                "Grund=weder Album-/Websuche noch Einzeltitel-Konsens "
                "noch MusicBrainz-Verweis | Einzelfallback wird "
                "übersprungen",
                group_key,
            )
            # Apple kennt dieses Album über keine Quelle. Eine allgemeine
            # Einzeltitel-Suche fände höchstens fremde Ausgaben und kostet
            # nur Zeit, deshalb gilt die Gruppe als abschließend behandelt.
            handled_indexes.update(indexes)
            continue

        options = []

        for candidate in album_candidates:
            logger.info(
                "APPLE LOOKUP AUFRUF | Schlüssel=%r | Collection-ID=%s | "
                "Store=%s | Score=%s",
                group_key,
                candidate.collection_id,
                candidate.country,
                candidate.confidence,
            )

            try:
                album_result = lookup_apple_album_by_id(
                    candidate.collection_id,
                    country=(candidate.country),
                )
            except DirectAlbumLookupError as error:
                logger.exception(
                    "APPLE LOOKUP FEHLER | Schlüssel=%r | "
                    "Collection-ID=%s | Store=%s | %s",
                    group_key,
                    candidate.collection_id,
                    candidate.country,
                    error,
                )
                continue

            matching = build_album_matching_result(
                group_songs,
                album_result,
            )
            logger.info(
                "APPLE MATCHING | Schlüssel=%r | Collection-ID=%s | "
                "Remote Tracks=%d | Matches=%r | Lokal ungematcht=%r",
                group_key,
                candidate.collection_id,
                len(album_result.tracks),
                [
                    (
                        match.local_index,
                        match.track.track,
                        match.track.title,
                        match.score,
                        match.confidence,
                    )
                    for match in matching.matches
                ],
                matching.unmatched_local_indexes,
            )
            options.append(
                (
                    _matching_rank(
                        matching,
                        album_result,
                        expected_track_count,
                        candidate.confidence,
                        preferred_store=(candidate.country == country.upper()),
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
            selected_collection_id = selected_candidate.collection_id
            logger.info(
                "APPLE OPTION GEWÄHLT | Schlüssel=%r | "
                "Collection-ID=%s | Store=%s | Rang=%r",
                group_key,
                selected_collection_id,
                selected_candidate.country,
                _best_rank,
            )
            selected_store = selected_candidate.country
            matched_local_indexes = set()

            for match in matching.matches:
                if match.confidence == "Mehrdeutig" and match.score < 80:
                    continue

                global_index = indexes[match.local_index]
                candidates_by_index[global_index].append(
                    replace(
                        match.track.as_candidate("apple_music"),
                        confidence=min(
                            100,
                            max(
                                0,
                                match.score,
                            ),
                        ),
                        release_id=(selected_collection_id),
                    )
                )
                matched_local_indexes.add(match.local_index)

            missing_local_indexes = [
                local_index
                for local_index in range(len(group_songs))
                if local_index not in matched_local_indexes
            ]
            logger.info(
                "APPLE FEHLENDE LOKALE TITEL | Schlüssel=%r | Lokale Indizes=%r",
                group_key,
                missing_local_indexes,
            )
        else:
            # Die Albumsuche kennt das Album, aber Lookup lieferte in keinem
            # Store eine verwendbare Trackliste. Wir nutzen dennoch die beste
            # sichere collectionId für eine streng albumgebundene Titelsuche.
            selected_candidate = max(
                album_candidates,
                key=lambda item: (
                    item.confidence,
                    item.country == country.upper(),
                ),
            )
            selected_collection_id = selected_candidate.collection_id
            selected_store = selected_candidate.country
            missing_local_indexes = list(range(len(group_songs)))

        recovery_countries = tuple(
            dict.fromkeys(
                (
                    selected_store,
                    country.upper(),
                    "US",
                )
            )
        )

        for local_index in missing_local_indexes:
            song = group_songs[local_index]
            wanted_track_number = _positive_int(song.track)
            wanted_disc_number = _positive_int(song.disc) or 1
            exact_track = None

            logger.info(
                "APPLE TRACK-NACHSUCHE | Schlüssel=%r | Lokalindex=%d | "
                "Titel=%r | Disc=%r | Track=%r | Collection-ID=%s | "
                "Stores=%r",
                group_key,
                local_index,
                song.title,
                wanted_disc_number,
                wanted_track_number,
                selected_collection_id,
                recovery_countries,
            )

            if wanted_track_number is not None:
                exact_track = find_apple_track_in_album(
                    selected_collection_id,
                    wanted_track_number,
                    wanted_disc_number,
                    countries=(recovery_countries),
                    lookup_func=(lookup_apple_album_by_id),
                )

            if exact_track is not None:
                logger.info(
                    "APPLE TRACK-NACHSUCHE ERFOLG | Schlüssel=%r | "
                    "Lokalindex=%d | Titel=%r | Remote=%r | Track=%r | "
                    "Song-ID=%r",
                    group_key,
                    local_index,
                    song.title,
                    exact_track.title,
                    exact_track.track,
                    exact_track.external_id,
                )
                candidates_by_index[indexes[local_index]].append(
                    replace(
                        exact_track.as_candidate("apple_music"),
                        confidence=100,
                        release_id=(selected_collection_id),
                    )
                )
                continue

            logger.warning(
                "APPLE SEARCH-FALLBACK START | Schlüssel=%r | Lokalindex=%d | Titel=%r",
                group_key,
                local_index,
                song.title,
            )

            try:
                recovered = search_song_in_album(
                    song.title,
                    (song.album_artist or song.artist),
                    song.album,
                    collection_id=(selected_collection_id),
                    alternate_title=(_title_from_filename(song.path)),
                    wanted_track=(song.track),
                    wanted_disc=(song.disc),
                    duration_ms=(_local_duration_ms(song.path)),
                    countries=(recovery_countries),
                    limit=200,
                )
            except AppleMusicProviderError as error:
                warnings_by_index[indexes[local_index]].append(str(error))
                continue

            logger.info(
                "APPLE SEARCH-FALLBACK RESULTAT | Schlüssel=%r | "
                "Lokalindex=%d | Treffer=%r",
                group_key,
                local_index,
                [
                    (
                        item.title,
                        item.track,
                        item.release_id,
                        item.external_id,
                        item.confidence,
                    )
                    for item in recovered
                ],
            )

            if recovered:
                candidates_by_index[indexes[local_index]].append(recovered[0])
            else:
                warnings_by_index[indexes[local_index]].append(
                    (
                        "Apple Music: Das Album wurde sicher erkannt, "
                        f"aber Disc {song.disc or '1'} / "
                        f"Track {song.track or '?'} konnte innerhalb "
                        f"der collectionId {selected_collection_id} "
                        "weder über die Lookup-API im "
                        "konfigurierten/US-Store noch über die streng "
                        "gefilterte Search-API gefunden werden. "
                        "Details stehen in logs/apple_music.log."
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


def _apple_candidate_via_musicbrainz(
    *,
    album_name: str,
    album_artist: str,
    wanted_year: str,
    expected_track_count: int | None,
    store: str,
) -> AppleAlbumCandidate | None:
    """
    Nutzt MusicBrainz als Brücke zur Apple-collectionId.

    Findet die iTunes-Suche das Album nicht, verweist die passende
    MusicBrainz-Release häufig direkt auf die Apple-Music-Albumseite.
    Aus deren collectionId lädt der bestehende Lookup-Pfad anschließend
    die korrekte, positionsrichtige Trackliste.
    """
    try:
        releases = search_mb_release(
            album_name,
            album_artist,
            expected_track_count=expected_track_count,
            wanted_year=wanted_year,
            limit=10,
        )
    except MusicBrainzProviderError:
        return None

    # Nur die beste Release-Übereinstimmung wird auf einen Apple-Verweis
    # geprüft. Das begrenzt die zusätzlichen MusicBrainz-Anfragen auf eine.
    for release in releases[:1]:
        if release.confidence < 65:
            continue

        collection_id = apple_collection_id_from_musicbrainz_release(
            release.release_id
        )

        if not collection_id:
            continue

        return AppleAlbumCandidate(
            collection_id=collection_id,
            album=album_name,
            artist=album_artist,
            track_count=expected_track_count or 0,
            year=wanted_year,
            country=store,
            confidence=90,
        )

    return None


def _apple_candidate_via_web_search(
    *,
    album_name: str,
    album_artist: str,
    wanted_year: str,
    expected_track_count: int | None,
    store: str,
) -> AppleAlbumCandidate | None:
    """
    Sucht die Apple-collectionId über die öffentliche Apple-Music-Websuche.

    Die iTunes-Such-API indexiert nicht jedes Album. Die Weboberfläche deckt
    dagegen den vollen Katalog ab; aus dem besten Treffer ergibt sich die
    collectionId, mit der der bestehende Lookup-Pfad die korrekte, positions-
    richtige Trackliste lädt.
    """
    candidates = search_albums_via_web(
        album_name,
        album_artist,
        expected_track_count=expected_track_count,
        wanted_year=wanted_year,
        country=store,
    )

    for candidate in candidates:
        if candidate.confidence >= MINIMUM_ALBUM_CONFIDENCE:
            return candidate

    return None


def _add_album_aware_musicbrainz_candidates(
    songs: list[Song],
    candidates_by_index: list[list[MetadataCandidate]],
    warnings_by_index: list[list[str]],
) -> set[int]:
    resolved_indexes: set[int] = set()

    for indexes in _album_groups(songs).values():
        group_songs = [songs[index] for index in indexes]
        album_name, album_artist, wanted_year, expected_track_count = _album_identity(
            group_songs
        )

        if not album_name:
            continue

        try:
            release_candidates = search_mb_release(
                album_name,
                album_artist,
                expected_track_count=(expected_track_count),
                wanted_year=wanted_year,
                limit=25,
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
                album_result = lookup_musicbrainz_release_by_id(candidate.release_id)
            except DirectAlbumLookupError:
                continue

            matching = build_album_matching_result(
                group_songs,
                album_result,
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
            if match.confidence == "Mehrdeutig" and match.score < 70:
                continue

            global_index = indexes[match.local_index]
            candidates_by_index[global_index].append(
                replace(
                    match.track.as_candidate("musicbrainz"),
                    confidence=min(
                        100,
                        max(0, match.score),
                    ),
                    release_id=(candidate.release_id),
                )
            )
            matched_local_indexes.add(match.local_index)
            resolved_indexes.add(global_index)

        # Nur wirklich zugeordnete Dateien gelten als erledigt.
        # Unklare oder fehlende Album-Matches dürfen anschließend noch
        # über die titelweise MusicBrainz-Suche ergänzt werden.
        unresolved_local_indexes = [
            local_index
            for local_index in range(len(group_songs))
            if local_index not in matched_local_indexes
        ]

        for local_index in unresolved_local_indexes:
            global_index = indexes[local_index]
            warnings_by_index[global_index].append(
                "MusicBrainz: Der Titel konnte der ausgewählten "
                "Release-Trackliste nicht sicher zugeordnet werden. "
                "Es wird zusätzlich eine titelweise Suche versucht."
            )

    return resolved_indexes


def _add_album_aware_deezer_candidates(
    songs: list[Song],
    candidates_by_index: list[list[MetadataCandidate]],
    warnings_by_index: list[list[str]],
) -> set[int]:
    """Lädt komplette Deezer-Alben und ordnet sie den lokalen Dateien zu.

    Deezers offizielle API liefert die volle Trackliste inklusive ISRC –
    dasselbe album-zentrierte Vorgehen wie bei Apple/MusicBrainz.
    """
    resolved_indexes: set[int] = set()

    for indexes in _album_groups(songs).values():
        group_songs = [songs[index] for index in indexes]
        album_name, album_artist, wanted_year, expected_track_count = _album_identity(
            group_songs
        )

        if not album_name:
            continue

        album_candidates = deezer.search_albums(
            album_name,
            album_artist,
            expected_track_count=expected_track_count,
        )
        best = next(
            (
                candidate
                for candidate in album_candidates
                if candidate.confidence >= deezer.MINIMUM_ALBUM_CONFIDENCE
            ),
            None,
        )

        if best is None:
            continue

        try:
            album_result = deezer.lookup_album(best.album_id)
        except DeezerProviderError as error:
            _append_group_warning(
                warnings_by_index,
                indexes,
                str(error),
            )
            continue

        matching = build_album_matching_result(
            group_songs,
            album_result,
        )

        for match in matching.matches:
            if match.confidence == "Mehrdeutig" and match.score < 70:
                continue

            global_index = indexes[match.local_index]
            candidates_by_index[global_index].append(
                replace(
                    match.track.as_candidate("deezer"),
                    confidence=min(100, max(0, match.score)),
                )
            )
            resolved_indexes.add(global_index)

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
        if not (match.confidence == "Mehrdeutig" and match.score < 70)
    ]
    exact_tracklist = int(len(album_result.tracks) == expected_track_count)

    return (
        len(accepted_matches),
        -len(matching.unmatched_local_indexes),
        exact_tracklist,
        sum(match.score for match in accepted_matches),
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
        directory = str(Path(song.path).parent.resolve()).casefold()
        groups[directory].append(index)

    return groups


def _album_identity(
    songs: list[Song],
) -> tuple[str, str, str, int]:
    album_name = _most_common_text(song.album for song in songs)
    album_artist = _most_common_text(
        (song.album_artist or song.artist) for song in songs
    )
    wanted_year = _year_only(_most_common_text(song.year for song in songs))
    expected_track_count = _most_common_positive_int(
        song.total_tracks for song in songs
    ) or len(songs)

    return (
        album_name,
        album_artist,
        wanted_year,
        expected_track_count,
    )


def _year_only(value: str) -> str:
    match = re.search(r"\b(19|20)\d{2}\b", str(value or ""))
    return match.group(0) if match else str(value or "").strip()


def _apple_album_title_variants(album: str) -> tuple[str, ...]:
    original = str(album or "").strip()
    if not original:
        return ()
    variants: list[str] = []

    def add(value: str) -> None:
        value = re.sub(r"\s+", " ", value).strip()
        if value and value.casefold() not in {item.casefold() for item in variants}:
            variants.append(value)

    add(original)
    add(original.replace("/", " "))
    add(original.replace("/", "-"))
    add(re.sub(r"[/_-]+", " ", original))
    return tuple(variants)


def _recover_apple_album_candidate_from_songs(
    songs: list[Song],
    *,
    album_name: str,
    album_artist: str,
    wanted_year: str,
    expected_track_count: int,
    countries: tuple[str, ...],
) -> AppleAlbumCandidate | None:
    logger = get_diagnostic_logger("proposal")
    unique_countries = tuple(
        dict.fromkeys(country.upper() for country in countries if country)
    )
    ranked_songs = sorted(
        enumerate(songs),
        key=lambda item: (
            -len(re.sub(r"\W+", "", item[1].title)),
            _positive_int(item[1].track) or 9999,
        ),
    )
    sampled = ranked_songs[: min(len(ranked_songs), 8)]
    sample_size = len(sampled)
    minimum_votes = min(sample_size, max(2, math.ceil(sample_size * 0.4)))
    voters: dict[str, set[int]] = defaultdict(set)
    stores: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, MetadataCandidate] = {}
    logger.info(
        "APPLE COLLECTION-RECOVERY START | Album=%r | Künstler=%r | Samples=%d | Mindeststimmen=%d | Stores=%r",
        album_name,
        album_artist,
        sample_size,
        minimum_votes,
        unique_countries,
    )
    for local_index, song in sampled:
        accepted_for_song: set[str] = set()
        for store in unique_countries:
            try:
                results = search_apple(
                    song.title,
                    song.album_artist or song.artist,
                    song.album,
                    alternate_title=_title_from_filename(song.path),
                    wanted_track=song.track,
                    wanted_disc=song.disc,
                    duration_ms=_local_duration_ms(song.path),
                    country=store,
                    limit=100,
                )
            except AppleMusicProviderError as error:
                logger.warning(
                    "APPLE COLLECTION-RECOVERY SUCHFEHLER | Lokalindex=%d | Store=%s | Titel=%r | %s",
                    local_index,
                    store,
                    song.title,
                    error,
                )
                continue
            suitable = [
                c
                for c in results
                if c.confidence >= MINIMUM_TRACK_CONFIDENCE
                and c.release_id
                and (
                    not c.album
                    or _normalized_text(c.album) == _normalized_text(album_name)
                )
                and (
                    not c.total_tracks
                    or _positive_int(c.total_tracks) in {None, expected_track_count}
                )
            ]
            logger.info(
                "APPLE COLLECTION-RECOVERY TITEL | Lokalindex=%d | Store=%s | Titel=%r | Treffer=%r",
                local_index,
                store,
                song.title,
                [
                    (
                        c.release_id,
                        c.title,
                        c.track,
                        c.album,
                        c.total_tracks,
                        c.confidence,
                    )
                    for c in suitable[:5]
                ],
            )
            for c in suitable[:3]:
                collection_id = c.release_id
                stores[collection_id][store] += 1
                examples.setdefault(collection_id, c)
                if collection_id in accepted_for_song:
                    continue
                accepted_for_song.add(collection_id)
                voters[collection_id].add(local_index)
        if voters:
            best_id, best_set = max(voters.items(), key=lambda item: len(item[1]))
            if len(best_set) >= minimum_votes:
                logger.info(
                    "APPLE COLLECTION-RECOVERY FRÜHER KONSENS | Collection-ID=%s | Stimmen=%d",
                    best_id,
                    len(best_set),
                )
                break
    if not voters:
        logger.warning("APPLE COLLECTION-RECOVERY ENDE | Keine Collection-ID")
        return None
    ranked = sorted(
        ((cid, len(indices)) for cid, indices in voters.items()),
        key=lambda item: (-item[1], item[0]),
    )
    best_id, best_votes = ranked[0]
    second_votes = ranked[1][1] if len(ranked) > 1 else 0
    if best_votes < minimum_votes or best_votes <= second_votes:
        logger.warning(
            "APPLE COLLECTION-RECOVERY UNEINDEUTIG | Stimmen=%r | Mindeststimmen=%d",
            ranked,
            minimum_votes,
        )
        return None
    store_counts = stores[best_id]
    store = next(
        (s for s in unique_countries if store_counts[s] == max(store_counts.values())),
        store_counts.most_common(1)[0][0],
    )
    example = examples[best_id]
    try:
        album_result = lookup_apple_album_by_id(best_id, country=store)
    except DirectAlbumLookupError as error:
        logger.warning(
            "APPLE COLLECTION-RECOVERY LOOKUP FEHLER | Collection-ID=%s | Store=%s | %s",
            best_id,
            store,
            error,
        )
        return None
    remote_count = len(album_result.tracks)
    matching_album = not album_result.album or _normalized_text(
        album_result.album
    ) == _normalized_text(album_name)
    count_plausible = (
        remote_count >= min(len(songs), expected_track_count)
        or remote_count == expected_track_count
    )
    if not matching_album or not count_plausible:
        logger.warning(
            "APPLE COLLECTION-RECOVERY VALIDIERUNG FEHLER | Collection-ID=%s | Remote-Album=%r | Remote-Tracks=%d | Erwartet=%d",
            best_id,
            album_result.album,
            remote_count,
            expected_track_count,
        )
        return None
    logger.info(
        "APPLE COLLECTION-RECOVERY ERFOLG | Collection-ID=%s | Store=%s | Stimmen=%d/%d | Album=%r | Remote-Tracks=%d",
        best_id,
        store,
        best_votes,
        sample_size,
        album_result.album,
        remote_count,
    )
    return AppleAlbumCandidate(
        collection_id=best_id,
        album=album_result.album or example.album or album_name,
        artist=album_result.album_artist or example.album_artist or album_artist,
        track_count=remote_count
        or _positive_int(example.total_tracks)
        or expected_track_count,
        year=_year_only(example.year) or wanted_year,
        country=store,
        confidence=min(99, 80 + best_votes * 3),
    )


def _normalized_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _warn_unmatched_album_tracks(
    matching,
    indexes: list[int],
    warnings_by_index: list[list[str]],
    *,
    source_label: str,
) -> None:
    for local_index in matching.unmatched_local_indexes:
        global_index = indexes[local_index]
        warnings_by_index[global_index].append(
            f"{source_label}: Dieser Titel konnte "
            "der vollständigen Albumtrackliste "
            "nicht sicher zugeordnet werden."
        )


def _add_safe_single_apple_candidate(
    song: Song,
    candidates: list[MetadataCandidate],
    warnings: list[str],
    *,
    country: str,
) -> None:
    stores = [
        country.upper(),
    ]

    if "US" not in stores:
        stores.append("US")

    all_results: list[MetadataCandidate] = []

    for store in stores:
        try:
            all_results.extend(
                search_apple(
                    song.title,
                    song.artist,
                    song.album,
                    alternate_title=(_title_from_filename(song.path)),
                    wanted_track=(song.track),
                    wanted_disc=(song.disc),
                    duration_ms=(_local_duration_ms(song.path)),
                    country=store,
                    limit=100,
                )
            )
        except AppleMusicProviderError as error:
            warnings.append(str(error))

        # Der bevorzugte Store liefert meist bereits Treffer. Der US-Store
        # wird nur noch als Rückfallebene abgefragt, wenn bislang nichts
        # gefunden wurde. Das halbiert die Anfragen im Normalfall.
        if all_results:
            break

    deduplicated = {}

    for result in all_results:
        key = result.external_id or (
            f"{result.release_id}:{result.disc}:{result.track}:{result.title}"
        )
        previous = deduplicated.get(key)

        if previous is None or result.confidence > previous.confidence:
            deduplicated[key] = result

    results = sorted(
        deduplicated.values(),
        key=lambda result: -result.confidence,
    )
    acceptable = next(
        (
            result
            for result in results
            if (result.confidence >= MINIMUM_TRACK_CONFIDENCE)
        ),
        None,
    )

    if acceptable is not None:
        candidates.append(
            _without_cross_release_position(
                acceptable,
                wanted_album=song.album,
            )
        )
    elif results:
        warnings.append(
            "Kein ausreichend sicherer Apple-Treffer. "
            f"„{results[0].title}“ wurde wegen nur "
            f"{results[0].confidence} % Sicherheit "
            "nicht übernommen."
        )


def _without_cross_release_position(
    candidate: MetadataCandidate,
    *,
    wanted_album: str,
) -> MetadataCandidate:
    """
    Entfernt Track-/Disc-Angaben aus Einzeltreffern fremder Alben.

    Ein Einzeltitel-Treffer aus einer Compilation oder einer fremden
    Ausgabe trägt die dortige Track-/Disc-Position. Diese darf die
    korrekte lokale beziehungsweise MusicBrainz-Position nicht
    überschreiben, solange das Album nicht übereinstimmt.
    """
    wanted = _normalized_text(wanted_album)
    found = _normalized_text(candidate.album)

    if not wanted or not found or wanted == found:
        return candidate

    if not (candidate.track or candidate.disc or candidate.total_tracks):
        return candidate

    return replace(
        candidate,
        track="",
        disc="",
        total_tracks="",
        total_discs="",
    )


def _proposal_result(
    song: Song,
    candidates: list[MetadataCandidate],
    warnings: list[str],
    *,
    primary_source: str,
    feature_handling: str,
) -> ProposalResult:
    by_source = {candidate.source: candidate for candidate in candidates}
    warning_map: dict[
        str,
        list[str],
    ] = {source: [] for source in supported_provider_ids()}

    for warning in warnings:
        lowered = warning.casefold()

        if "musicbrainz" in lowered:
            warning_map.setdefault(
                "musicbrainz",
                [],
            ).append(warning)
        elif "deezer" in lowered:
            warning_map.setdefault(
                "deezer",
                [],
            ).append(warning)
        elif "apple" in lowered or "store" in lowered or "collectionid" in lowered:
            warning_map.setdefault(
                "apple_music",
                [],
            ).append(warning)

    sources: dict[
        str,
        SourceProposal,
    ] = {}

    for source in supported_provider_ids():
        candidate = by_source.get(source)
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
                    for warning in source_warnings
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
            feature_handling=(feature_handling),
            primary_source=(primary_source),
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
    supported = list(supported_provider_ids())

    if selected_provider in supported:
        supported.remove(selected_provider)

        return [
            selected_provider,
            *supported,
        ]

    return supported


def _positive_int(
    value,
) -> int | None:
    try:
        number = int(value)
    except (
        TypeError,
        ValueError,
    ):
        return None

    return number if number > 0 else None


def _append_group_warning(
    warnings_by_index: list[list[str]],
    indexes: list[int],
    warning: str,
) -> None:
    for index in indexes:
        warnings_by_index[index].append(warning)


def _most_common_text(
    values,
) -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]

    if not cleaned:
        return ""

    return Counter(cleaned).most_common(1)[0][0]


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

    return Counter(numbers).most_common(1)[0][0]


def _title_from_filename(
    filepath: str,
) -> str:
    return title_from_filename(filepath)


def _local_duration_ms(
    filepath: str,
) -> int | None:
    return local_duration_ms(filepath)
