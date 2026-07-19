from musictagstudio.media_library.client import RequestTrace
from musictagstudio.media_library.controller import (
    ArtistRelation,
    CatalogSearchController,
)
from musictagstudio.ui.media_library_widget import MediaLibraryWidget


class IdentityClient:
    def get_json(self, endpoint, params, *, result_key):
        return (
            {
                "relations": [
                    {
                        "target-type": "artist",
                        "type": "is person",
                        "direction": "forward",
                        "artist": {
                            "id": "yaenniver-id",
                            "name": "YAENNIVER",
                            "disambiguation": "Jennifer Weist",
                        },
                        "attributes": [],
                    },
                    {
                        "target-type": "artist",
                        "type": "member of band",
                        "direction": "forward",
                        "artist": {
                            "id": "band-id",
                            "name": "Jennifer Rostock",
                        },
                        "attributes": ["vocals"],
                    },
                ],
                "aliases": [],
            },
            RequestTrace("url", "200", 1),
        )


def test_identity_and_membership_relations_keep_ids_and_roles():
    result = CatalogSearchController(IdentityClient()).load_artist_relations(
        "person-id"
    )

    identity = next(r for r in result.relations if r.relation_type == "is person")
    membership = next(
        r for r in result.relations if r.relation_type == "member of band"
    )
    assert identity.target_id == "yaenniver-id"
    assert identity.name == "YAENNIVER"
    assert membership.attributes == ("vocals",)


def test_identity_relations_have_distinct_categories():
    identity = ArtistRelation(
        "is person", "artist", "stage-id", "Stage Name", direction="forward"
    )
    person = ArtistRelation(
        "is person", "artist", "person-id", "Real Name", direction="backward"
    )
    alias = ArtistRelation("alias", "alias", "same-id", "Name Variant")

    assert MediaLibraryWidget._relation_category(identity) == "Künstleridentitäten"
    assert MediaLibraryWidget._relation_category(person) == "Person"
    assert MediaLibraryWidget._relation_category(alias) == "Namensvarianten"
