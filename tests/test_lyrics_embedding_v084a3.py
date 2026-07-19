from pathlib import Path

import pytest

from musictagstudio.lyrics import LyricsDocument, LyricsLine
from musictagstudio.lyrics import embedding


def synced_document():
    return LyricsDocument(
        plain_text="Hallo",
        synced_lines=(LyricsLine(1000, "Hallo"),),
        source="LRCLIB",
    )


def test_embedding_plan_warns_when_mp4_cannot_preserve_sync(tmp_path):
    plan = embedding.build_embedding_plan(tmp_path / "song.m4a", synced_document())

    assert plan.supported
    assert not plan.preserves_sync
    assert "nur der Klartext" in plan.warning


def test_embedding_requires_explicit_confirmation(tmp_path):
    path = tmp_path / "song.flac"
    path.write_bytes(b"audio")

    with pytest.raises(PermissionError, match="bestätigter Vorschau"):
        embedding.embed_lyrics(path, synced_document())


def test_embedding_removes_backup_after_success(monkeypatch, tmp_path):
    path = tmp_path / "song.flac"
    path.write_bytes(b"original")
    monkeypatch.setattr(
        embedding,
        "_write_for_suffix",
        lambda target, _document: target.write_bytes(b"changed"),
    )

    embedding.embed_lyrics(path, synced_document(), confirmed=True)

    assert path.read_bytes() == b"changed"
    assert not list(tmp_path.glob("*.lyrics-backup-*"))


def test_embedding_restores_audio_after_writer_error(monkeypatch, tmp_path):
    path = tmp_path / "song.flac"
    path.write_bytes(b"original")

    def broken_writer(target: Path, _document):
        target.write_bytes(b"broken")
        raise OSError("Schreibfehler")

    monkeypatch.setattr(embedding, "_write_for_suffix", broken_writer)

    with pytest.raises(OSError, match="Schreibfehler"):
        embedding.embed_lyrics(path, synced_document(), confirmed=True)

    assert path.read_bytes() == b"original"


def test_id3_writes_plain_and_synchronised_frames(monkeypatch, tmp_path):
    class Tags:
        def __init__(self):
            self.frames = []
            self.deleted = []

        def delall(self, key):
            self.deleted.append(key)

        def add(self, frame):
            self.frames.append(frame)

        def save(self, path, v2_version):
            self.saved = (path, v2_version)

    tags = Tags()
    monkeypatch.setattr(embedding, "ID3", lambda _path: tags)

    embedding._write_id3(tmp_path / "song.mp3", synced_document())

    assert tags.deleted == ["USLT", "SYLT"]
    assert {type(frame).__name__ for frame in tags.frames} == {"USLT", "SYLT"}
    assert tags.saved[1] == 3
