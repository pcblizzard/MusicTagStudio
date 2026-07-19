from musictagstudio.media_library.discogs import DiscogsRelease
from musictagstudio.ui.media_library_widget import _label_artist_statistics


def release(title, year, *artists):
    return DiscogsRelease(
        source_id=title,
        title=title,
        year=year,
        artists=artists,
    )


def test_label_artists_include_release_count_and_period():
    statistics = _label_artist_statistics(
        [
            release("Maske", "2004", "Sido"),
            release("Ich", "2006", "Sido"),
            release("Staatsfeind Nr. 1", "2005", "Bushido"),
            release("Sampler", "2007", "Various"),
        ]
    )

    assert statistics == [
        ("Sido", 2, "2004", "2006"),
        ("Bushido", 1, "2005", "2005"),
    ]


def test_label_artist_names_are_normalized_for_aggregation():
    statistics = _label_artist_statistics(
        [
            release("A", "2004", "Bushido"),
            release("B", "2005", "BUSHIDO"),
        ]
    )

    assert statistics == [("Bushido", 2, "2004", "2005")]
