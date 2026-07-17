from pathlib import Path

from musictagstudio.library_sources import (
    IndexedAlbum,
    MusicSource,
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
