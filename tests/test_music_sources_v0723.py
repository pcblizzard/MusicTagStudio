
from musictagstudio.library_sources import (
    IndexedAlbum,
    MusicSource,
    SourceScanSummary,
    merge_scan_results,
    update_source_availability,
)
from musictagstudio.settings import (
    AppSettings,
    load_settings,
    save_settings,
)


def test_settings_roundtrip_multiple_sources(
    tmp_path,
):
    config = tmp_path / "config.toml"
    settings = AppSettings(
        music_sources=(
            MusicSource(
                source_id="one",
                name="SSD",
                path=r"D:\Musik",
                enabled=True,
            ),
            MusicSource(
                source_id="two",
                name="Archiv",
                path=r"E:\Archiv",
                enabled=False,
            ),
        ),
        load_sources_on_startup=True,
        scan_sources_on_startup=True,
    )

    save_settings(
        settings,
        config,
    )
    loaded = load_settings(
        config
    )

    assert len(loaded.music_sources) == 2
    assert loaded.music_sources[0].name == "SSD"
    assert loaded.music_sources[1].enabled is False
    assert loaded.load_sources_on_startup is True
    assert loaded.scan_sources_on_startup is True


def test_offline_album_is_retained(
    tmp_path,
):
    missing = tmp_path / "missing"
    source = MusicSource(
        source_id="source",
        name="USB",
        path=str(missing),
        enabled=True,
    )
    album = IndexedAlbum(
        key="artist|album|folder",
        album="Album",
        album_artist="Artist",
        folder=str(missing / "Artist" / "Album"),
        representative_file=str(
            missing / "Artist" / "Album" / "01.flac"
        ),
        source_id="source",
        source_name="USB",
        source_path=str(missing),
        source_online=True,
        track_count=10,
        last_seen="2026-01-01",
    )

    updated = update_source_availability(
        [album],
        (source,),
    )

    assert len(updated) == 1
    assert updated[0].source_online is False


def test_refresh_removes_albums_from_deleted_source(tmp_path):
    current_source = MusicSource(
        source_id="current",
        name="Music",
        path=str(tmp_path),
    )
    stale_album = IndexedAlbum(
        key="old|album|folder",
        album="Old Album",
        album_artist="Old Artist",
        folder=str(tmp_path / "old"),
        representative_file=str(tmp_path / "old" / "01.flac"),
        source_id="removed-source",
        source_name="Old Music",
        source_path=str(tmp_path / "old-source"),
        source_online=False,
        track_count=100,
        last_seen="2026-01-01",
    )
    current_album = IndexedAlbum(
        key="new|album|folder",
        album="New Album",
        album_artist="New Artist",
        folder=str(tmp_path / "new"),
        representative_file=str(tmp_path / "new" / "01.flac"),
        source_id="current",
        source_name="Music",
        source_path=str(tmp_path),
        source_online=True,
        track_count=14,
        last_seen="2026-07-22",
    )
    summary = SourceScanSummary(
        source=current_source,
        albums=(current_album,),
        song_count=14,
        failure_count=0,
    )

    merged = merge_scan_results(
        [stale_album],
        [summary],
        (current_source,),
    )

    assert merged == [current_album]
