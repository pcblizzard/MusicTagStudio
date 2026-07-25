from pathlib import Path

from musictagstudio.lyrics.models import LyricsDocument
from musictagstudio.lyrics import search as lyrics_search
from musictagstudio.models.song import Song


def test_local_search_includes_embedded_lyrics(monkeypatch, tmp_path) -> None:
    audio_path = tmp_path / "01 - Gib mir was Echtes.flac"
    audio_path.write_bytes(b"not real audio")
    song = Song(
        path=str(audio_path),
        title="Gib mir was Echtes",
        artist="Clueso",
        album="Deja Vu 1/2",
    )

    monkeypatch.setattr(
        lyrics_search,
        "read_embedded_lyrics_variants",
        lambda _path: (
            LyricsDocument(
                plain_text=(
                    "Rutsch' durch die Wohnung, denn auf allem hier liegt Staub"
                ),
                source="Eingebettete Lyrics (LYRICS)",
            ),
        ),
    )
    monkeypatch.setattr(
        lyrics_search,
        "LyricsCache",
        lambda: type("EmptyCache", (), {"path": Path(tmp_path / "empty.sqlite")})(),
    )
    database_path = tmp_path / "empty.sqlite"
    with lyrics_search.connect_database(database_path) as connection:
        connection.execute(
            "CREATE TABLE lyrics_cache "
            "(cache_key TEXT, document_json TEXT)"
        )

    results = lyrics_search.search_local_lyrics(
        "Rutsch' durch die Wohnung",
        songs=(song,),
    )

    assert len(results) == 1
    assert results[0].source == "Eingebettete Lyrics"
    assert results[0].title == "Gib mir was Echtes"
    assert results[0].local_path == str(audio_path)
    assert "Rutsch' durch die Wohnung" in results[0].excerpt
