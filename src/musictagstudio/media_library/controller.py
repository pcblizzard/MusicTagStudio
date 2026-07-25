from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from .client import (
    MusicBrainzClient,
    RequestTrace,
    default_client,
)
from .service import (
    ArtistCandidate,
    ReleaseGroup,
    _artist_candidates,
    _normalise_artist_name,
    _parse_release_groups,
)


@dataclass(frozen=True)
class ArtistSearchResponse:
    query: str
    artists: tuple[ArtistCandidate, ...]
    exact_match: bool
    suggestion_mode: bool
    traces: tuple[RequestTrace, ...]


@dataclass(frozen=True)
class ReleaseGroupResponse:
    artist_id: str
    release_groups: tuple[ReleaseGroup, ...]
    traces: tuple[RequestTrace, ...]


@dataclass(frozen=True)
class ArtistRelation:
    relation_type: str
    target_type: str
    target_id: str
    name: str
    direction: str = ""
    begin: str = ""
    end: str = ""
    ended: bool = False
    disambiguation: str = ""
    attributes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtistRelationsResponse:
    artist_id: str
    relations: tuple[ArtistRelation, ...]
    traces: tuple[RequestTrace, ...]


class CatalogSearchController:
    def __init__(
        self,
        client: MusicBrainzClient | None = None,
    ) -> None:
        self.client = client or default_client

    def suggest_artists(
        self,
        query: str,
        *,
        limit: int = 8,
        preferred_country: str = "",
    ) -> ArtistSearchResponse:
        query = str(query or "").strip()
        if len(query) < 3:
            return ArtistSearchResponse(query, (), False, False, ())
        request_limit = max(1, min(int(limit), 20))
        candidate_limit = max(25, request_limit)
        escaped = self._lucene_escape(query)
        payload, trace = self.client.get_json(
            "artist",
            {
                "query": f"artist:{escaped}* OR artist:{escaped}",
                "limit": candidate_limit,
            },
            result_key="artists",
        )
        artists = self._rank_candidates(
            query,
            _artist_candidates(payload),
            preferred_country=preferred_country,
        )
        wanted = _normalise_artist_name(query)
        artists.sort(
            key=lambda artist: (
                _live_match_rank(wanted, _normalise_artist_name(artist.name)),
                -int(artist.score or 0),
                artist.name.casefold(),
            )
        )
        return ArtistSearchResponse(
            query=query,
            artists=tuple(artists[:request_limit]),
            exact_match=self._has_exact_match(query, artists),
            suggestion_mode=True,
            traces=(trace,),
        )

    def search_artists(
        self,
        query: str,
        *,
        limit: int = 25,
        preferred_country: str = "",
    ) -> ArtistSearchResponse:
        query = str(
            query or ""
        ).strip()
        if not query:
            return ArtistSearchResponse(
                query="",
                artists=(),
                exact_match=False,
                suggestion_mode=False,
                traces=(),
            )

        request_limit = max(
            1,
            min(
                int(limit),
                100,
            ),
        )
        traces: list[
            RequestTrace
        ] = []

        # 1) Standard indexed search. This is the most reliable endpoint.
        payload, trace = self.client.get_json(
            "artist",
            {
                "query": query,
                "limit": request_limit,
            },
            result_key="artists",
        )
        traces.append(
            trace
        )
        artists = _artist_candidates(
            payload
        )
        exact = self._has_exact_match(
            query,
            artists,
        )

        if exact:
            return ArtistSearchResponse(
                query=query,
                artists=tuple(
                    self._rank_candidates(
                        query,
                        artists,
                        preferred_country=preferred_country,
                    )
                ),
                exact_match=exact,
                suggestion_mode=False,
                traces=tuple(
                    traces
                ),
            )

        # 2) Explicit artist field search.
        candidates = list(artists)
        payload, trace = self.client.get_json(
            "artist",
            {
                "query": (
                    f'artist:"{self._lucene_escape(query)}"'
                ),
                "limit": request_limit,
            },
            result_key="artists",
        )
        traces.append(
            trace
        )
        field_artists = _artist_candidates(
            payload
        )
        exact = self._has_exact_match(
            query,
            field_artists,
        )
        if exact:
            return ArtistSearchResponse(
                query=query,
                artists=tuple(
                    self._rank_candidates(
                        query,
                        field_artists,
                        preferred_country=preferred_country,
                    )
                ),
                exact_match=exact,
                suggestion_mode=False,
                traces=tuple(
                    traces
                ),
            )
        candidates.extend(field_artists)

        # 3) MusicBrainz/Lucene fuzzy terms for typographical errors.
        terms = re.findall(
            r"[\wÀ-ÖØ-öø-ÿ]+",
            query,
            flags=re.UNICODE,
        )
        fuzzy_query = " ".join(
            f"artist:{self._lucene_escape(term)}~0.75"
            for term in terms
            if len(term) >= 3
        )
        if fuzzy_query:
            payload, trace = self.client.get_json(
                "artist",
                {
                    "query": fuzzy_query,
                    "limit": request_limit,
                },
                result_key="artists",
            )
            traces.append(
                trace
            )
            candidates.extend(_artist_candidates(
                payload
            ))

        artists = self._rank_candidates(
            query,
            candidates,
            preferred_country=preferred_country,
        )

        return ArtistSearchResponse(
            query=query,
            artists=tuple(
                artists
            ),
            exact_match=False,
            suggestion_mode=bool(
                artists
            ),
            traces=tuple(
                traces
            ),
        )

    @staticmethod
    def _rank_candidates(
        query: str,
        artists: list[ArtistCandidate],
        *,
        preferred_country: str = "",
    ) -> list[ArtistCandidate]:
        wanted = _normalise_artist_name(query)
        unique = {
            artist.artist_id: artist
            for artist in artists
        }

        preferred = str(preferred_country or "").strip().upper()

        def similarity(artist: ArtistCandidate) -> tuple[float, float, int]:
            names = (
                _normalise_artist_name(artist.name),
                _normalise_artist_name(artist.sort_name),
            )
            ratio = max(
                SequenceMatcher(None, wanted, name).ratio()
                for name in names
            )
            regional = int(bool(preferred) and artist.country.upper() == preferred)
            regional_score = ratio + (0.06 if regional else 0.0)
            return regional_score, ratio, artist.score

        return sorted(
            unique.values(),
            key=similarity,
            reverse=True,
        )

    def load_release_groups(
        self,
        artist_id: str,
        *,
        limit: int = 300,
    ) -> ReleaseGroupResponse:
        groups: list[
            ReleaseGroup
        ] = []
        traces: list[
            RequestTrace
        ] = []
        offset = 0
        page_size = 100

        while offset < limit:
            payload, trace = self.client.get_json(
                "release-group",
                {
                    "artist": artist_id,
                    "limit": min(
                        page_size,
                        limit - offset,
                    ),
                    "offset": offset,
                },
                result_key="release-groups",
            )
            traces.append(
                trace
            )
            raw_groups = payload.get(
                "release-groups",
                [],
            )
            groups.extend(
                _parse_release_groups(
                    raw_groups
                )
            )

            offset += len(
                raw_groups
            )
            total = int(
                payload.get(
                    "release-group-count",
                    0,
                )
                or 0
            )
            if (
                not raw_groups
                or offset >= total
            ):
                break

        unique = {
            group.release_group_id: group
            for group in groups
        }
        ordered = sorted(
            unique.values(),
            key=lambda group: (
                group.first_release_date
                or "9999",
                group.title.casefold(),
            ),
        )
        return ReleaseGroupResponse(
            artist_id=artist_id,
            release_groups=tuple(
                ordered
            ),
            traces=tuple(
                traces
            ),
        )


    def load_artist_relations(
        self,
        artist_id: str,
    ) -> ArtistRelationsResponse:
        payload, trace = self.client.get_json(
            f"artist/{artist_id}",
            {"inc": "artist-rels+label-rels+aliases"},
            result_key="relations",
        )
        relations: list[ArtistRelation] = []
        for item in payload.get("relations", []):
            if not isinstance(item, dict):
                continue
            target_type = str(item.get("target-type", ""))
            target = item.get(target_type, {})
            if not isinstance(target, dict):
                continue
            target_id = str(target.get("id", ""))
            name = str(target.get("name", "")).strip()
            if not target_id or not name:
                continue
            relations.append(
                ArtistRelation(
                    relation_type=str(item.get("type", "")).strip(),
                    target_type=target_type,
                    target_id=target_id,
                    name=name,
                    direction=str(item.get("direction", "")),
                    begin=str(item.get("begin", "") or ""),
                    end=str(item.get("end", "") or ""),
                    ended=bool(item.get("ended", False)),
                    disambiguation=str(target.get("disambiguation", "") or ""),
                    attributes=tuple(
                        str(value).strip()
                        for value in item.get("attributes", [])
                        if str(value).strip()
                    ),
                )
            )

        # Aliases are part of the artist payload, not the relation list.
        # Model them like the other links so the UI can group and navigate
        # them consistently.
        for alias in payload.get("aliases", []):
            if not isinstance(alias, dict):
                continue
            name = str(alias.get("name", "")).strip()
            if not name:
                continue
            relations.append(
                ArtistRelation(
                    relation_type="alias",
                    target_type="alias",
                    target_id=artist_id,
                    name=name,
                    disambiguation=str(alias.get("type", "") or ""),
                )
            )
        unique = {
            (r.target_type, r.target_id, r.relation_type, r.direction): r
            for r in relations
        }
        ordered = sorted(
            unique.values(),
            key=lambda r: (r.relation_type.casefold(), r.name.casefold()),
        )
        return ArtistRelationsResponse(
            artist_id=artist_id,
            relations=tuple(ordered),
            traces=(trace,),
        )

    @staticmethod
    def _has_exact_match(
        query: str,
        artists: list[
            ArtistCandidate
        ],
    ) -> bool:
        wanted = _normalise_artist_name(
            query
        )
        return any(
            wanted
            in {
                _normalise_artist_name(
                    artist.name
                ),
                _normalise_artist_name(
                    artist.sort_name
                ),
            }
            for artist in artists
        )

    @staticmethod
    def _lucene_escape(
        value: str,
    ) -> str:
        return re.sub(
            r'([+\-!(){}\[\]^"~*?:\\/])',
            r"\\\1",
            value.strip(),
        )


def _live_match_rank(query: str, name: str) -> int:
    if name.startswith(query):
        return 0
    if any(part.startswith(query) for part in name.split()):
        return 1
    if query in name:
        return 2
    return 3


default_controller = CatalogSearchController()
