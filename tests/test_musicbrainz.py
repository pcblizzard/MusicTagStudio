from musictagstudio.providers.musicbrainz import (
    _best_tag,
    _candidate_from_recording,
    _optional_int,
)


def test_musicbrainz_recording_parser():
    payload = {
        "id": "rec-id",
        "title": "Song",
        "score": 92,
        "length": 123000,
        "isrcs": ["DEABC1234567"],
        "artist-credit": [{"name": "Main", "joinphrase": " feat. "}, {"name": "Guest"}],
        "tags": [{"name": "hip hop", "count": 5}],
        "releases": [
            {
                "id": "rel-id",
                "title": "Album",
                "date": "1997-01-01",
                "artist-credit": [{"name": "Main"}],
                "label-info": [{"label": {"name": "Label X"}}],
                "media": [
                    {
                        "position": 1,
                        "track-count": 10,
                        "tracks": [
                            {"number": "2", "recording": {"id": "rec-id"}}
                        ],
                    }
                ],
            }
        ],
    }
    result = _candidate_from_recording(payload)
    assert result.isrc == "DEABC1234567"
    assert result.label == "Label X"
    assert result.track == "2"
    assert result.total_tracks == "10"
    assert result.year == "1997"


def test_musicbrainz_numeric_json_values_are_parsed_defensively():
    assert _optional_int("12") == 12
    assert _optional_int(7) == 7
    assert _optional_int({"unexpected": "value"}) is None
    assert _best_tag(
        [
            {"name": "invalid", "count": {"unexpected": "value"}},
            {"name": "pop", "count": "4"},
        ]
    ) == "pop"
