from __future__ import annotations

from musictagstudio.models.song import Song
from musictagstudio.services.favorites import Favorites
from musictagstudio.services.listening_stats import (
    ListeningStats,
    format_duration,
)


# --- Favorites ---------------------------------------------------------------

def test_favorite_toggle_and_persist(tmp_path):
    path = tmp_path / "fav.json"
    fav = Favorites(path)
    assert not fav.is_favorite("artist", "Clueso")
    assert fav.toggle("artist", "Clueso") is True
    assert fav.is_favorite("artist", "clueso")  # casefold
    # neu geladen -> persistiert
    assert Favorites(path).is_favorite("artist", "Clueso")
    assert fav.toggle("artist", "Clueso") is False
    assert not Favorites(path).is_favorite("artist", "Clueso")


def test_favorite_song_uses_exact_path(tmp_path):
    fav = Favorites(tmp_path / "f.json")
    fav.add("song", "/Music/A.flac")
    assert fav.is_favorite("song", "/Music/A.flac")
    assert not fav.is_favorite("song", "/music/a.flac")  # Pfad exakt


# --- Listening stats ---------------------------------------------------------

def _song(**kw):
    return Song(**kw)


def test_record_aggregates_all_dimensions(tmp_path):
    stats = ListeningStats(tmp_path / "s.json")
    song = _song(path="a.flac", artist="A", album="Alb", genre="Rock")
    stats.record(song, 100)
    stats.record(song, 50)
    assert stats.total("song", "a.flac") == 150
    assert stats.total("artist", "A") == 150
    assert stats.total("genre", "Rock") == 150


def test_album_artist_preferred_for_artist_bucket(tmp_path):
    stats = ListeningStats(tmp_path / "s.json")
    stats.record(_song(path="x", artist="Feat", album_artist="Main"), 60)
    assert stats.total("artist", "Main") == 60
    assert stats.total("artist", "Feat") == 0


def test_short_plays_ignored(tmp_path):
    stats = ListeningStats(tmp_path / "s.json")
    stats.record(_song(path="a", genre="Rock"), 2)  # < 5s
    assert stats.total("genre", "Rock") == 0


def test_top_and_persistence(tmp_path):
    path = tmp_path / "s.json"
    stats = ListeningStats(path)
    stats.record(_song(path="a", genre="Rock"), 300)
    stats.record(_song(path="b", genre="Pop"), 100)
    top = ListeningStats(path).top("genre", 2)
    assert top[0] == ("Rock", 300.0)
    assert top[1] == ("Pop", 100.0)


def test_format_duration():
    assert format_duration(30) == "30 Sek"
    assert format_duration(90) == "1 Min"
    assert format_duration(3661) == "1 Std 1 Min"
    assert format_duration(90000) == "1 Tage 1 Std"
