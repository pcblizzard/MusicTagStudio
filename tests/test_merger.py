from musictagstudio.core.merger import apply_merged_metadata, merge_metadata, song_values
from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song


def test_apple_is_master_and_musicbrainz_supplements():
    local = Song(title="Alt", artist="Main", album="Album", path="x.flac")
    apple = MetadataCandidate(
        source="apple_music",
        confidence=90,
        title="Neu [feat. Guest]",
        artist="Main",
        album="Album",
        track="2",
        total_tracks="10",
        isrc="APPLE",
    )
    mb = MetadataCandidate(
        source="musicbrainz",
        confidence=85,
        title="MB Titel",
        artist="Main",
        isrc="DEABC1234567",
        label="Label X",
    )
    merged = merge_metadata(local, [apple, mb])
    assert merged.values["title"] == "Neu"
    assert merged.values["artist"] == "Main, Guest"
    assert merged.sources["title"] == "apple_music"
    assert merged.values["isrc"] == "DEABC1234567"
    assert merged.sources["isrc"] == "musicbrainz"

    updated = apply_merged_metadata(local, merged, {"title", "artist", "isrc"})
    assert updated.title == "Neu"
    assert updated.artist == "Main, Guest"
    assert updated.isrc == "DEABC1234567"
    assert song_values(local)["title"] == "Alt"
