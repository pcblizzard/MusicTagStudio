from types import SimpleNamespace

from musictagstudio.lyrics.duration import read_duration_seconds


def test_duration_is_read_from_mutagen_info(monkeypatch):
    monkeypatch.setattr(
        "musictagstudio.lyrics.duration.File",
        lambda *_args, **_kwargs: SimpleNamespace(
            info=SimpleNamespace(length=213.45)
        ),
    )

    assert read_duration_seconds("song.flac") == 213.45


def test_unreadable_duration_returns_zero(monkeypatch):
    monkeypatch.setattr(
        "musictagstudio.lyrics.duration.File",
        lambda *_args, **_kwargs: None,
    )

    assert read_duration_seconds("missing.flac") == 0.0
