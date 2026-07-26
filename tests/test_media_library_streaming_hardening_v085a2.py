from pathlib import Path


SOURCE = (
    Path(__file__).parents[1]
    / "src"
    / "musictagstudio"
    / "ui"
    / "media_library_widget.py"
).read_text(encoding="utf-8")
STREAMING_SERVICE_SOURCE = (
    Path(__file__).parents[1]
    / "src"
    / "musictagstudio"
    / "media_library"
    / "streaming"
    / "service.py"
).read_text(encoding="utf-8")


def test_streaming_search_uses_known_release_context() -> None:
    assert "expected_track_count=expected_track_count" in SOURCE
    assert "_streaming_artist(group.artist, self.current_artist_name)" in SOURCE


def test_streaming_result_requires_safe_confidence() -> None:
    assert (
        "candidate.confidence >= MINIMUM_ALBUM_CONFIDENCE"
        in STREAMING_SERVICE_SOURCE
    )


def test_stale_streaming_result_is_ignored() -> None:
    assert "self.current_group.release_group_id != group_id" in SOURCE


def test_tracklist_reserves_space_for_multiple_rows() -> None:
    assert "self.track_table.setMinimumHeight(190)" in SOURCE
    assert "self.detail_splitter = QSplitter(Qt.Orientation.Vertical)" in SOURCE


def test_cover_list_uses_compact_rows() -> None:
    assert "max(64,list_cover+10)" in SOURCE


def test_discography_headers_sort_children_within_categories() -> None:
    assert "sectionClicked.connect(" in SOURCE
    assert "def _sort_discography_column" in SOURCE


def test_release_views_replace_unknown_artist_placeholder() -> None:
    assert "display_artist = (" in SOURCE
    assert "_streaming_artist(group.artist, self.current_artist_name)" in SOURCE
    assert "values=(group.title,display_artist" in SOURCE


def test_source_card_has_room_for_wrapped_provenance() -> None:
    assert "self.source_details.setMinimumHeight(72)" in SOURCE
    assert "self.source_details.setMaximumHeight(96)" in SOURCE
    assert "metadata_scroll.setWidgetResizable(True)" in SOURCE
    assert 'f"{parts[0]}, {parts[1]} + {len(parts) - 2} weitere"' in SOURCE
    assert "self.source_details.setToolTip" in SOURCE


def test_streaming_result_survives_view_changes_and_restart() -> None:
    assert "self._streaming_results" in SOURCE
    assert "def _save_streaming_result" in SOURCE
    assert "def _load_saved_streaming_result" in SOURCE
    assert "StreamingAvailabilityCache" in SOURCE
    assert "ttl_days=7" in SOURCE
    assert 'strftime("%d.%m.%Y, %H:%M")' in SOURCE


def test_every_successful_streaming_check_shows_its_timestamp() -> None:
    # Zeitstempel-/Gespeichert-Hinweis sind i18n-basiert (tr-Keys).
    assert '"last_checked_at"' in SOURCE
    assert '"saved_result_prefix"' in SOURCE
    assert "+ checked_hint" in SOURCE
