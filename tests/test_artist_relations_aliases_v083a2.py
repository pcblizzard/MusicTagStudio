from musictagstudio.media_library.client import RequestTrace
from musictagstudio.media_library.controller import CatalogSearchController


class AliasClient:
    def get_json(self, endpoint, params, *, result_key):
        assert endpoint == "artist/artist-id"
        assert params == {"inc": "artist-rels+label-rels"}
        return (
            {
                "relations": [],
                "aliases": [
                    {"name": "Example Alias", "type": "Artist name"},
                    {"name": ""},
                ],
            },
            RequestTrace(
                url="https://musicbrainz.org/ws/2/artist/artist-id",
                status="200",
                elapsed_ms=1,
                result_count=1,
                from_cache=False,
            ),
        )


def test_artist_aliases_are_returned_as_navigable_relations():
    result = CatalogSearchController(AliasClient()).load_artist_relations(
        "artist-id"
    )

    assert len(result.relations) == 1
    alias = result.relations[0]
    assert alias.name == "Example Alias"
    assert alias.target_type == "alias"
    assert alias.target_id == "artist-id"
    assert alias.relation_type == "alias"
