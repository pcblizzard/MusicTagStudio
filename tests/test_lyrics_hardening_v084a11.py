from musictagstudio.lyrics import (
    LyricsCache,
    LyricsDocument,
    LyricsRequest,
    LyricsResolver,
    live_version_warning,
    lyrics_cache_key,
)


def test_local_cache_round_trip(tmp_path):
    cache = LyricsCache(tmp_path / "lyrics.sqlite3")
    key = lyrics_cache_key("Titel", "Künstler", "Album", 123.4)
    document = LyricsDocument(
        plain_text="Text",
        source="LRCLIB",
        provider_id="42",
        fetched_at=LyricsDocument.now_iso(),
    )

    cache.put(key, document)

    assert cache.get(key) == document


def test_live_version_warns_for_unmarked_album_lyrics():
    request = LyricsRequest(
        "song.flac",
        "Song (Live)",
        "Band",
        "Konzert",
        200,
    )
    document = LyricsDocument(
        plain_text="Text",
        source="LRCLIB",
        metadata={"ti": "Song", "al": "Studioalbum"},
    )

    warning = live_version_warning(request, document)

    assert "Live-Version" in warning
    assert "abweichen" in warning


def test_explicit_live_lyrics_need_no_warning():
    request = LyricsRequest("song.flac", "Song (Live)", "Band", "Live", 200)
    document = LyricsDocument(
        plain_text="Text",
        source="LRCLIB",
        metadata={"ti": "Song (Live)"},
    )

    assert live_version_warning(request, document) == ""


def test_resolver_prefers_sidecar_before_embedded_and_cache(monkeypatch, tmp_path):
    audio = tmp_path / "song.flac"
    sidecar = tmp_path / "song.lrc"
    sidecar.write_text("Lokaler Text", encoding="utf-8")
    monkeypatch.setattr(
        "musictagstudio.lyrics.resolver.read_embedded_lyrics_variants",
        lambda _path: (LyricsDocument(plain_text="Tag", source="Tag"),),
    )
    cache = LyricsCache(tmp_path / "cache.sqlite3")
    cache.put(
        lyrics_cache_key("Song", "Band", "Album", 200),
        LyricsDocument(plain_text="Cache", source="LRCLIB"),
    )

    result = LyricsResolver(cache=cache).local(
        LyricsRequest(str(audio), "Song", "Band", "Album", 200)
    )

    assert result.selected is not None
    assert result.selected.source == "LRC-Datei"
    assert [item.source for item in result.candidates] == [
        "LRC-Datei",
        "Tag",
        "LRCLIB",
    ]
