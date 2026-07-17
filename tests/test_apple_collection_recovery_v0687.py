from musictagstudio.models.metadata import MetadataCandidate
from musictagstudio.models.song import Song
from musictagstudio.services import proposal
from musictagstudio.direct_album_lookup import DirectAlbumResult, DirectAlbumTrack

def cand(title,track):
    return MetadataCandidate(source="apple_music",confidence=100,title=title,artist="Clueso",album_artist="Clueso",album="Deja Vu 1/2",year="2026",track=track,total_tracks="14",disc="1",total_discs="1",external_id=f"song-{track}",release_id="1859696286")

def test_collection_recovery(monkeypatch):
    songs=[Song(title=t,artist="Clueso",album_artist="Clueso",album="Deja Vu 1/2",year="2026-02-27",track=str(i),total_tracks="14",disc="1",path=f"C:/Album/{i}.flac") for i,t in enumerate(["Gib mir was Echtes","Liebe auf den letzten Blick","Freier Fall"],1)]
    monkeypatch.setattr(proposal,"search_apple",lambda title,*a,**kw:[cand(title,kw["wanted_track"])])
    monkeypatch.setattr(proposal,"_local_duration_ms",lambda p:None)
    monkeypatch.setattr(proposal,"lookup_apple_album_by_id",lambda cid,*,country:DirectAlbumResult(provider="apple_music",album="Deja Vu 1/2",album_artist="Clueso",tracks=tuple(DirectAlbumTrack(title=f"Track {n}",artist="Clueso",album_artist="Clueso",album="Deja Vu 1/2",genre="Pop",year="2026",track=str(n),total_tracks="14",disc="1",total_discs="1") for n in range(1,15))))
    result=proposal._recover_apple_album_candidate_from_songs(songs,album_name="Deja Vu 1/2",album_artist="Clueso",wanted_year="2026",expected_track_count=14,countries=("DE","US"))
    assert result and result.collection_id=="1859696286" and result.track_count==14

def test_year_only(): assert proposal._year_only("2026-02-27")=="2026"
def test_variants(): assert "Deja Vu 1 2" in proposal._apple_album_title_variants("Deja Vu 1/2")
