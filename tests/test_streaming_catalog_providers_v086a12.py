from __future__ import annotations

from musictagstudio.media_library.streaming import service
from musictagstudio.media_library.streaming.models import AvailabilityStatus
from musictagstudio.providers import spotify, tidal
from musictagstudio.providers.streaming_catalog import (
    CatalogAlbumCandidate,
    album_confidence,
    core_album_key,
)


def _confidence(wanted: str, album: str, *, year_match=True, tracks_match=True) -> int:
    return album_confidence(
        wanted_album=wanted,
        wanted_artist="Danger Dan",
        wanted_year="2023",
        expected_track_count=16,
        album=album,
        artist="Danger Dan",
        year="2023" if year_match else "2022",
        track_count=16 if tracks_match else 15,
    )


def test_live_edition_suffix_variants_match_via_core_title():
    # MusicBrainz: "(Live In Berlin)", Streaming-Dienste: "(Live)".
    wanted = "Das ist alles von der Kunstfreiheit gedeckt (Live In Berlin)"
    album = "Das ist alles von der Kunstfreiheit gedeckt (Live)"
    assert core_album_key(wanted) == core_album_key(album)
    # Ohne Jahres-/Trackbonus liegt der Wert dank Kern-Treffer trotzdem >= 70.
    assert _confidence(wanted, album, year_match=False, tracks_match=False) >= 70


def test_studio_and_live_versions_are_not_confused():
    # Studio-Titel (kein Zusatz) darf die Live-Version NICHT als Treffer werten.
    wanted = "Das ist alles von der Kunstfreiheit gedeckt (Live In Berlin)"
    studio = "Das ist alles von der Kunstfreiheit gedeckt"
    # Kein Kern-Bonus (Studio hat keinen Zusatz) -> nur Teilstring 38 + 25 < 70.
    assert _confidence(wanted, studio, year_match=False, tracks_match=False) < 70


def test_exact_title_still_scores_highest():
    title = "Das ist alles von der Kunstfreiheit gedeckt (Live)"
    assert _confidence(title, title) >= 90


def test_spotify_album_search_uses_catalog_metadata(monkeypatch):
    responses = iter(
        [
            {"access_token": "spotify-token", "expires_in": 3600},
            {
                "albums": {
                    "items": [
                        {
                            "id": "spotify-album",
                            "name": "Deja Vu 1/2",
                            "artists": [{"name": "Clueso"}],
                            "release_date": "2026-02-27",
                            "total_tracks": 14,
                            "external_urls": {
                                "spotify": "https://open.spotify.com/album/test"
                            },
                        }
                    ]
                }
            },
        ]
    )
    monkeypatch.setattr(spotify, "_cached_token", "")
    monkeypatch.setattr(spotify, "request_json", lambda _request: next(responses))

    result = spotify.search_albums(
        "Deja Vu 1/2",
        "Clueso",
        client_id="client",
        client_secret="secret",
        expected_track_count=14,
        wanted_year="2026",
    )

    assert result[0].external_id == "spotify-album"
    assert result[0].confidence == 100


def test_spotify_search_strips_parenthetical_suffix(monkeypatch):
    captured: list[str] = []
    responses = iter(
        [
            {"access_token": "spotify-token", "expires_in": 3600},
            {
                "albums": {
                    "items": [
                        {
                            "id": "live-album",
                            "name": "Das ist alles von der Kunstfreiheit gedeckt (Live)",
                            "artists": [{"name": "Danger Dan"}],
                            "release_date": "2023-06-02",
                            "total_tracks": 16,
                        }
                    ]
                }
            },
        ]
    )

    def fake(request):
        captured.append(getattr(request, "full_url", ""))
        return next(responses)

    monkeypatch.setattr(spotify, "_cached_token", "")
    monkeypatch.setattr(spotify, "request_json", fake)

    result = spotify.search_albums(
        "Das ist alles von der Kunstfreiheit gedeckt (Live In Berlin)",
        "Danger Dan",
        client_id="client",
        client_secret="secret",
        expected_track_count=16,
        wanted_year="2023",
    )

    # Die Suchquery enthält den Kern-Titel ohne den Klammerzusatz.
    search_url = captured[-1]
    assert "Berlin" not in search_url
    assert "Kunstfreiheit" in search_url
    # Trotz abweichendem Zusatz („Live" statt „Live In Berlin") ein Treffer.
    assert result and result[0].confidence >= 70


def test_tidal_album_search_parses_json_api_included_resources(monkeypatch):
    requested_urls: list[str] = []
    responses = iter(
        [
            {"access_token": "tidal-token", "expires_in": 3600},
            {
                "included": [
                    {
                        "id": "tidal-album",
                        "type": "albums",
                    }
                ]
            },
            {
                "data": [
                    {
                        "id": "tidal-album",
                        "type": "albums",
                        "attributes": {
                            "title": "Deja Vu 1/2",
                            "releaseDate": "2026-02-27",
                            "numberOfItems": 14,
                            "externalLinks": [
                                {"href": ("https://tidal.com/browse/album/tidal-album")}
                            ],
                        },
                        "relationships": {
                            "artists": {
                                "data": [{"id": "artist-id", "type": "artists"}]
                            }
                        },
                    }
                ],
                "included": [
                    {
                        "id": "artist-id",
                        "type": "artists",
                        "attributes": {"name": "Clueso"},
                    }
                ],
            },
        ]
    )
    monkeypatch.setattr(tidal, "_cached_token", "")
    monkeypatch.setattr(tidal, "get_user_access_token", lambda *a, **k: "")

    def fake_request_json(request):
        requested_urls.append(request.full_url)
        return next(responses)

    monkeypatch.setattr(tidal, "request_json", fake_request_json)

    result = tidal.search_albums(
        "Deja Vu 1/2",
        "Clueso",
        client_id="client",
        client_secret="secret",
        expected_track_count=14,
        wanted_year="2026",
    )

    assert result[0].external_id == "tidal-album"
    assert result[0].artist == "Clueso"
    assert result[0].track_count == 14
    assert result[0].external_url == ("https://tidal.com/browse/album/tidal-album")
    assert result[0].confidence == 100
    assert "/v2/searchResults/" in requested_urls[1]
    assert "Deja%20Vu%201%202" in requested_urls[1]
    assert "include=albums" in requested_urls[1]
    assert "filter%5Bid%5D=tidal-album" in requested_urls[2]
    assert "include=artists" in requested_urls[2]


def test_streaming_service_combines_configured_providers(monkeypatch):
    monkeypatch.setattr(
        service,
        "search_album_variants",
        lambda *_args, **_kwargs: [],
    )
    candidate = CatalogAlbumCandidate(
        provider="tidal",
        external_id="tidal-album",
        external_url="https://tidal.com/browse/album/tidal-album",
        album="Deja Vu 1/2",
        artist="Clueso",
        year="2026",
        track_count=14,
        confidence=100,
        country="DE",
    )
    monkeypatch.setattr(
        service,
        "search_tidal_albums",
        lambda *_args, **_kwargs: [candidate],
    )

    report = service.check_streaming_providers(
        "Deja Vu 1/2",
        "Clueso",
        expected_track_count=14,
        track_titles=(),
        wanted_year="2026",
        country="DE",
        tidal_client_id="client",
        tidal_client_secret="secret",
    )

    assert report.results["apple_music"].status is AvailabilityStatus.NOT_FOUND
    assert report.results["tidal"].status is AvailabilityStatus.AVAILABLE
    assert "spotify" not in report.results


def test_streaming_service_keeps_other_results_after_unexpected_error(monkeypatch):
    monkeypatch.setattr(
        service,
        "search_album_variants",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "search_tidal_albums",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("unexpected provider defect")
        ),
    )

    report = service.check_streaming_providers(
        "Album",
        "Artist",
        expected_track_count=10,
        track_titles=(),
        wanted_year="2026",
        country="DE",
        tidal_client_id="client",
        tidal_client_secret="secret",
    )

    assert report.results["apple_music"].status is AvailabilityStatus.NOT_FOUND
    assert "tidal" in report.errors
