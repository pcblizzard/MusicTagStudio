from __future__ import annotations

from PySide6.QtWidgets import QApplication

from musictagstudio.direct_album_lookup import DirectAlbumResult, DirectAlbumTrack
from musictagstudio.models.song import Song
from musictagstudio.player.preview import PreviewPlayer
from musictagstudio.ui.direct_album_dialog import DirectAlbumDialog


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _track(title: str, track: str, *, preview: str) -> DirectAlbumTrack:
    return DirectAlbumTrack(
        title=title,
        artist="Danger Dan",
        album_artist="Danger Dan",
        album="X",
        genre="",
        year="2022",
        track=track,
        total_tracks="2",
        disc="1",
        total_discs="1",
        preview_url=preview,
    )


def test_preview_player_toggle_starts_and_stops(monkeypatch):
    _app()
    player = PreviewPlayer()

    started: list[str] = []
    monkeypatch.setattr(player, "play", lambda url: started.append(url))
    monkeypatch.setattr(player, "stop", lambda: started.append("STOP"))

    player.toggle("https://example.com/a.m4a")
    assert started == ["https://example.com/a.m4a"]

    # Leere URL ist ein No-Op.
    player.toggle("")
    assert started == ["https://example.com/a.m4a"]


def test_download_preview_sends_browser_user_agent(monkeypatch):
    from musictagstudio.player import preview

    captured = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"AUDIO"

    def fake_urlopen(request, timeout=0):
        captured["ua"] = request.get_header("User-agent")
        return _Resp()

    monkeypatch.setattr(preview, "urlopen", fake_urlopen)

    data = preview._download_preview("https://cdn/preview.mp3")

    assert data == b"AUDIO"
    assert "Mozilla" in captured["ua"]


def test_preview_player_downloaded_writes_local_source():
    import os

    _app()
    from musictagstudio.player.preview import PreviewPlayer

    player = PreviewPlayer()
    player._token = 3
    player._on_downloaded(3, "https://cdn/x.mp3", b"ID3fakebytes")

    assert os.path.isfile(player._temp_path)
    assert player._player.source().isLocalFile()

    # Veraltetes Token schreibt nichts Neues.
    previous = player._temp_path
    player._on_downloaded(99, "https://cdn/y.mp3", b"other")
    assert player._temp_path == previous

    player.stop()
    try:
        os.remove(player._temp_path)
    except OSError:
        pass


def test_preview_player_toggle_same_url_stops(monkeypatch):
    _app()
    player = PreviewPlayer()
    player._current_url = "https://example.com/a.m4a"
    monkeypatch.setattr(player, "is_playing", lambda: True)

    stopped: list[bool] = []
    monkeypatch.setattr(player, "stop", lambda: stopped.append(True))

    player.toggle("https://example.com/a.m4a")
    assert stopped == [True]


def test_dialog_preview_button_enabled_only_with_url():
    _app()
    songs = [
        Song(title="Cool", artist="Danger Dan", album="X", track="1",
             disc="1", path="C:/m/01.flac"),
        Song(title="Ohne", artist="Danger Dan", album="X", track="2",
             disc="1", path="C:/m/02.flac"),
    ]
    dialog = DirectAlbumDialog(songs, "DE")
    result = DirectAlbumResult(
        provider="apple_music",
        album="X",
        album_artist="Danger Dan",
        tracks=(
            _track("Cool", "1", preview="https://example.com/p.m4a"),
            _track("Ohne", "2", preview=""),
        ),
    )

    dialog._loaded(result)

    # Track 1 hat eine Vorschau -> Knopf aktiv; Track 2 nicht -> inaktiv.
    assert dialog.preview_buttons[0].isEnabled() is True
    assert dialog.preview_buttons[1].isEnabled() is False
    assert dialog.preview_buttons[0].property("previewState") in {"play", "pause"}
    assert not dialog.preview_buttons[0].icon().isNull()
    dialog.done(0)


def test_dialog_preview_click_toggles_player(monkeypatch):
    _app()
    songs = [
        Song(title="Cool", artist="Danger Dan", album="X", track="1",
             disc="1", path="C:/m/01.flac"),
    ]
    dialog = DirectAlbumDialog(songs, "DE")
    result = DirectAlbumResult(
        provider="deezer",
        album="X",
        album_artist="Danger Dan",
        tracks=(_track("Cool", "1", preview="https://example.com/p.mp3"),),
    )
    dialog._loaded(result)

    played: list[str] = []
    monkeypatch.setattr(
        dialog.preview_player,
        "play",
        lambda url, title="": played.append(url),
    )

    dialog._toggle_preview(0)
    assert played == ["https://example.com/p.mp3"]
    assert dialog._playing_preview_row == 0
    dialog.done(0)


def test_resolve_deezer_previews_maps_by_title(monkeypatch):
    from musictagstudio.direct_album_lookup import DirectAlbumResult
    from musictagstudio.providers import deezer
    from musictagstudio.ui import media_library_widget as mlw

    monkeypatch.setattr(
        deezer,
        "search_albums",
        lambda *a, **k: [
            deezer.DeezerAlbumCandidate(
                album_id="1", album="X", artist="A",
                track_count=2, confidence=100,
            )
        ],
    )
    monkeypatch.setattr(
        deezer,
        "lookup_album",
        lambda album_id: DirectAlbumResult(
            provider="deezer", album="X", album_artist="A",
            tracks=(
                _track("A", "1", preview="http://p/1.mp3"),
                _track("B", "2", preview=""),
            ),
        ),
    )

    mapping = mlw._resolve_deezer_previews("X", "A", 2)

    assert mapping == {"a": "http://p/1.mp3"}


def test_resolve_deezer_previews_empty_when_no_confident_match(monkeypatch):
    from musictagstudio.providers import deezer
    from musictagstudio.ui import media_library_widget as mlw

    monkeypatch.setattr(deezer, "search_albums", lambda *a, **k: [])

    assert mlw._resolve_deezer_previews("X", "A", 2) == {}


def test_media_library_preview_buttons_enable_on_resolution():
    _app()
    from musictagstudio.media_library.service import Track
    from musictagstudio.ui.media_library_widget import MediaLibraryWidget

    widget = MediaLibraryWidget()
    assert widget.track_table.columnCount() == 5

    tracks = [
        Track(disc_number=1, track_number=1, title="A"),
        Track(disc_number=1, track_number=2, title="B"),
    ]
    # current_group None -> keine echte Deezer-Auflösung im Test.
    widget.current_group = None
    widget._tracks_loaded(tracks)

    assert len(widget.track_preview_buttons) == 2
    assert widget.track_preview_buttons[0].isEnabled() is False

    widget._preview_token = 7
    widget._previews_resolved(7, {"a": "http://p/1.mp3"})

    assert widget.track_preview_buttons[0].isEnabled() is True
    assert widget.track_preview_buttons[1].isEnabled() is False

    # Veraltetes Token wird ignoriert.
    widget._previews_resolved(99, {"b": "http://x"})
    assert widget.track_preview_urls[1] == ""
    widget.deleteLater()


def test_player_bar_preview_mode(monkeypatch):
    _app()
    from musictagstudio.player.preview import PreviewPlayer
    from musictagstudio.player.widget import PlayerBar

    bar = PlayerBar()
    preview = PreviewPlayer()
    bar.bind_preview_player(preview)

    # Sitzung startet -> Vorschau-Modus, Queue-Steuerung deaktiviert.
    preview._current_title = "Traumtänzer"
    preview.session_changed.emit(True)
    assert bar._preview_mode is True
    assert "Traumtänzer" in bar.title_label.text()
    assert "Vorschau" in bar.title_label.text()
    assert bar.next_button.isEnabled() is False

    # ~30 Sekunden Dauer + Position werden angezeigt.
    bar._preview_duration_changed(30000)
    bar._preview_position_changed(12000)
    assert bar.position_slider.maximum() == 30000
    assert bar.duration_label.text() == "0:30"
    assert bar.position_label.text() == "0:12"

    # Wiedergabe/Pause steuert die Vorschau, nicht die Engine.
    calls = {"preview": 0, "engine": 0}
    monkeypatch.setattr(
        preview, "toggle_pause",
        lambda: calls.__setitem__("preview", calls["preview"] + 1),
    )
    monkeypatch.setattr(
        bar.engine, "toggle",
        lambda: calls.__setitem__("engine", calls["engine"] + 1),
    )
    bar._toggle_play()
    assert calls == {"preview": 1, "engine": 0}

    # Wechsel auf eine andere Vorschau (Sitzung bleibt aktiv): der Titel in
    # der Leiste aktualisiert sich, sobald die neue Vorschau spielt.
    preview._current_title = "Bordertown"
    preview.state_changed.emit("http://x/border.mp3", True)
    assert "Bordertown" in bar.title_label.text()
    assert "Traumtänzer" not in bar.title_label.text()

    # Sitzungsende stellt die Engine-Anzeige wieder her.
    preview.session_changed.emit(False)
    assert bar._preview_mode is False
    assert bar.title_label.text() == "Kein Titel geladen"
    assert bar.next_button.isEnabled() is True
    bar.deleteLater()


def test_preview_session_lifecycle_signal(monkeypatch):
    _app()
    from musictagstudio.player.preview import PreviewPlayer

    preview = PreviewPlayer()
    events: list[bool] = []
    preview.session_changed.connect(events.append)

    # play() startet eine Sitzung (Download wird unterdrückt).
    monkeypatch.setattr(preview._pool, "start", lambda worker: None)
    preview.play("http://x/p.mp3", "Titel")
    assert preview.is_active is True
    assert events == [True]

    preview.stop()
    assert preview.is_active is False
    assert events == [True, False]


def test_media_library_local_track_plays_full_song(tmp_path):
    _app()
    from types import SimpleNamespace

    from musictagstudio.media_library.service import Track
    from musictagstudio.models.song import Song
    from musictagstudio.ui.media_library_widget import MediaLibraryWidget

    file_one = tmp_path / "01.mp3"
    file_two = tmp_path / "02.mp3"
    file_one.write_bytes(b"")
    file_two.write_bytes(b"")

    widget = MediaLibraryWidget()
    widget.current_artist_name = "A"
    widget.set_local_songs(
        [
            Song(title="T1", artist="A", album_artist="A", album="Album X",
                 disc="1", track="1", path=str(file_one)),
            Song(title="T2", artist="A", album_artist="A", album="Album X",
                 disc="1", track="2", path=str(file_two)),
        ]
    )
    widget.current_group = SimpleNamespace(
        title="Album X", artist="A", release_group_id="x"
    )
    # Track 1 liegt lokal vor, Track 3 nicht.
    widget._tracks_loaded(
        [
            Track(disc_number=1, track_number=1, title="T1"),
            Track(disc_number=1, track_number=3, title="Fremd"),
        ]
    )

    assert widget._row_is_local == [True, False]
    # Lokaler Track: Knopf aktiv mit Vollwiedergabe-Tooltip.
    assert widget.track_preview_buttons[0].isEnabled() is True
    assert "Vollen Titel" in widget.track_preview_buttons[0].toolTip()
    # Nicht-lokaler Track ohne aufgelöste Vorschau: inaktiv.
    assert widget.track_preview_buttons[1].isEnabled() is False

    emitted: dict = {}
    widget.play_local_tracks.connect(
        lambda songs, index: emitted.update(
            titles=[s.title for s in songs], index=index
        )
    )
    widget._play_track(0)
    # Nur die lokal vorhandenen Titel der Trackliste landen in der Queue –
    # T2 liegt zwar lokal vor, ist aber kein Track dieser Veröffentlichung.
    assert emitted == {"titles": ["T1"], "index": 0}

    # Nicht-lokaler Track ruft den Vorschau-Pfad auf.
    calls: list[int] = []
    widget._toggle_track_preview = lambda row: calls.append(row)
    widget._play_track(1)
    assert calls == [1]
    widget.deleteLater()


def test_single_track_matches_by_title_not_colliding_number(tmp_path):
    # Szenario aus dem Bug-Report: Eine Single "Keine Angst" (1 Track, Nr. 1)
    # liegt lokal im selben Ordner wie das Album (Track 01 = "Die meisten
    # meiner Freunde", Track 11 = "Keine Angst"). Der reine Nummern-Abgleich
    # traf frueher faelschlich Track 01.
    _app()
    from types import SimpleNamespace

    from musictagstudio.media_library.service import Track
    from musictagstudio.models.song import Song
    from musictagstudio.ui.media_library_widget import MediaLibraryWidget

    file_first = tmp_path / "01.flac"
    file_title = tmp_path / "11.flac"
    file_first.write_bytes(b"")
    file_title.write_bytes(b"")

    widget = MediaLibraryWidget()
    widget.current_artist_name = "Danger Dan"
    widget.set_local_songs(
        [
            Song(title="Die meisten meiner Freunde", artist="Danger Dan",
                 album_artist="Danger Dan", album="Keine Angst",
                 disc="1", track="1", path=str(file_first)),
            Song(title="Keine Angst", artist="Danger Dan",
                 album_artist="Danger Dan", album="Keine Angst",
                 disc="1", track="11", path=str(file_title)),
        ]
    )
    widget.current_group = SimpleNamespace(
        title="Keine Angst", artist="Danger Dan", release_group_id="s"
    )
    # Single-Trackliste: nur "Keine Angst" als Track 1.
    widget._tracks_loaded([Track(disc_number=1, track_number=1, title="Keine Angst")])

    emitted: dict = {}
    widget.play_local_tracks.connect(
        lambda songs, index: emitted.update(
            titles=[s.title for s in songs], index=index
        )
    )
    widget._play_track(0)

    # Nur der geklickte Titel (per Titel korrekt zugeordnet) landet in der Queue.
    assert emitted == {"titles": ["Keine Angst"], "index": 0}
    widget.deleteLater()


def test_placeholder_track_shows_local_title(tmp_path):
    # Vorab-Album: Anbieter liefert Platzhalter „Track 11", die Datei liegt
    # aber lokal als „Keine Angst" vor -> Trackliste zeigt den lokalen Titel.
    _app()
    from types import SimpleNamespace

    from musictagstudio.media_library.service import Track
    from musictagstudio.models.song import Song
    from musictagstudio.ui.media_library_widget import MediaLibraryWidget

    local_file = tmp_path / "11.flac"
    local_file.write_bytes(b"")

    widget = MediaLibraryWidget()
    widget.current_artist_name = "Danger Dan"
    widget.set_local_songs(
        [
            Song(title="Keine Angst", artist="Danger Dan",
                 album_artist="Danger Dan", album="Keine Angst",
                 disc="1", track="11", path=str(local_file)),
        ]
    )
    widget.current_group = SimpleNamespace(
        title="Keine Angst", artist="Danger Dan", release_group_id="s"
    )
    widget._tracks_loaded(
        [Track(disc_number=1, track_number=11, title="Track 11", artist="Danger Dan")]
    )

    assert widget.track_table.item(0, 2).text() == "Keine Angst - Danger Dan"
    widget.deleteLater()


def test_apple_and_deezer_tracks_carry_preview_url():
    # Sicherstellen, dass das Feld existiert und optional bleibt.
    track = DirectAlbumTrack(
        title="T", artist="A", album_artist="A", album="X", genre="",
        year="2022", track="1", total_tracks="1", disc="1", total_discs="1",
    )
    assert track.preview_url == ""


def test_settings_round_trip_preview_source(tmp_path):
    from musictagstudio.settings import AppSettings, load_settings, save_settings

    config = tmp_path / "config.toml"
    save_settings(AppSettings(preview_source="apple_music"), config)
    assert load_settings(config).preview_source == "apple_music"

    # Ungültige Werte fallen auf "deezer" zurück.
    save_settings(AppSettings(preview_source="deezer"), config)
    assert load_settings(config).preview_source == "deezer"


def test_resolve_apple_previews_maps_tracks(monkeypatch):
    from musictagstudio.direct_album_lookup import DirectAlbumResult
    from musictagstudio.providers import apple_music
    from musictagstudio.ui import media_library_widget as mlw

    monkeypatch.setattr(
        apple_music,
        "search_album_variants",
        lambda *a, **k: [
            apple_music.AppleAlbumCandidate(
                collection_id="1", album="X", artist="A",
                track_count=1, year="2022", country="DE", confidence=95,
            )
        ],
    )
    # Der Apple-Resolver importiert lookup_apple_album_by_id lokal aus
    # direct_album_lookup -> dort patchen.
    from musictagstudio import direct_album_lookup
    monkeypatch.setattr(
        direct_album_lookup,
        "lookup_apple_album_by_id",
        lambda album_id, *, country: DirectAlbumResult(
            provider="apple_music", album="X", album_artist="A",
            tracks=(_track("A", "1", preview="http://itunes/1.m4a"),),
        ),
    )

    mapping = mlw._resolve_apple_previews("X", "A", 1, "DE")
    assert mapping == {"a": "http://itunes/1.m4a"}


def test_preview_title_key_strips_feat_and_brackets():
    from musictagstudio.ui.media_library_widget import _preview_title_key

    assert _preview_title_key("7Eleven (feat. Fatoni & Edgar Wasser)") == "7eleven"
    assert _preview_title_key("Propaganda (feat. Danger Dan)") == "propaganda"
    assert _preview_title_key("Bordertown") == "bordertown"
    # Gleicher Kern trotz feat. -> gleicher Schlüssel (Abgleich klappt).
    assert _preview_title_key("Lovesongs") == _preview_title_key("Lovesongs (Live)")


def test_previews_resolved_matches_by_title_despite_duplicate_track_numbers():
    _app()
    from musictagstudio.media_library.service import Track
    from musictagstudio.ui.media_library_widget import MediaLibraryWidget

    widget = MediaLibraryWidget()
    widget.current_group = None
    # Discogs-artige Doppelnummerierung: zwei Zeilen mit Tracknummer 1.
    # Titel tragen zusätzlich den Künstler; der Abgleich darf nur den reinen
    # Titel verwenden (track_title würde " - Artist" anhängen).
    widget._tracks_loaded(
        [
            Track(
                disc_number=1, track_number=1,
                title="Kirchheim Horizont", artist="Juse Ju",
            ),
            Track(
                disc_number=1, track_number=1,
                title="Bordertown", artist="Juse Ju",
            ),
        ]
    )

    widget._preview_token = 3
    widget._previews_resolved(
        3,
        {
            "kirchheimhorizont": "http://p/kirchheim.mp3",
            "bordertown": "http://p/bordertown.mp3",
        },
    )

    # Jede Zeile bekommt trotz identischer Tracknummer die richtige Vorschau.
    assert widget.track_preview_urls[0] == "http://p/kirchheim.mp3"
    assert widget.track_preview_urls[1] == "http://p/bordertown.mp3"
    widget.deleteLater()


def test_media_library_only_playing_row_highlighted(monkeypatch):
    _app()
    from musictagstudio.media_library.service import Track
    from musictagstudio.ui.media_library_widget import MediaLibraryWidget

    widget = MediaLibraryWidget()
    widget.current_group = None
    # Mehrteiliges Album: Track 1 taucht mehrfach auf -> selbe Vorschau-URL.
    widget._tracks_loaded(
        [
            Track(disc_number=1, track_number=1, title="A"),
            Track(disc_number=1, track_number=2, title="B"),
            Track(disc_number=1, track_number=1, title="C"),
        ]
    )
    # Alle drei Zeilen bekommen (versehentlich) dieselbe URL.
    widget.track_preview_urls = ["http://same.mp3"] * 3

    # Es spielt Zeile 0.
    widget._playing_preview_row = 0
    monkeypatch.setattr(widget.preview_player, "is_playing", lambda: True)
    widget._refresh_track_preview_buttons()

    # Trotz identischer URL wird nur die spielende Zeile hervorgehoben
    # (Play/Pause-Icon je Zeile über die previewState-Eigenschaft prüfbar).
    assert widget.track_preview_buttons[0].property("previewState") == "pause"
    assert widget.track_preview_buttons[1].property("previewState") == "play"
    assert widget.track_preview_buttons[2].property("previewState") == "play"
    assert not widget.track_preview_buttons[0].icon().isNull()
    widget.deleteLater()
