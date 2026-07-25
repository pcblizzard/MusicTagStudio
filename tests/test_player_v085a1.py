import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from musictagstudio.models.song import Song
from musictagstudio.player import PlaybackQueue, PlayerBar, PlayerEngine, QueueDialog
from musictagstudio.player.model import format_milliseconds
from musictagstudio.ui.media_library_widget import _tag_number


def songs() -> list[Song]:
    return [
        Song(title="One", artist="Artist", path="one.flac"),
        Song(title="Two", artist="Artist", path="two.flac"),
        Song(title="Three", artist="Artist", path="three.flac"),
    ]


def test_playback_queue_navigates_without_wrapping():
    queue = PlaybackQueue()
    assert queue.replace(songs(), 1).title == "Two"
    assert queue.next().title == "Three"
    assert queue.next() is None
    assert queue.previous().title == "Two"


def test_repeat_all_wraps_and_repeat_one_replays_automatically():
    queue = PlaybackQueue()
    queue.replace(songs(), 2)
    queue.repeat_mode = "all"

    assert queue.next().title == "One"

    queue.repeat_mode = "one"
    assert queue.next(automatic=True).title == "One"
    assert queue.next().title == "Two"


def test_shuffle_uses_each_remaining_title(monkeypatch):
    queue = PlaybackQueue()
    queue.replace(songs(), 0)
    queue.set_shuffle(True)
    monkeypatch.setattr("random.choice", lambda values: values[0])

    first = queue.next()
    second = queue.next()

    assert {first.title, second.title} == {"Two", "Three"}
    assert queue.next() is None


def test_history_shuffle_restores_the_same_forward_title(monkeypatch):
    queue = PlaybackQueue()
    queue.replace(songs(), 0)
    queue.set_shuffle(True)
    monkeypatch.setattr("random.choice", lambda values: values[-1])

    random_title = queue.next()
    assert random_title.title == "Three"
    assert queue.previous().title == "One"
    assert queue.next().title == "Three"


def test_fresh_shuffle_draws_new_titles_for_both_directions(monkeypatch):
    queue = PlaybackQueue()
    queue.replace(songs(), 0)
    queue.shuffle_mode = "fresh"
    monkeypatch.setattr("random.choice", lambda values: values[0])

    forward = queue.next()
    backward = queue.previous()

    assert forward.title == "Two"
    assert backward.title == "Three"
    assert queue.next().title == "One"


def test_queue_can_move_remove_and_clear_titles():
    queue = PlaybackQueue()
    queue.replace(songs(), 0)

    queue.move_next(2)
    assert [song.title for song in queue.songs] == ["One", "Three", "Two"]
    assert queue.current.title == "One"

    queue.remove(1)
    assert [song.title for song in queue.songs] == ["One", "Two"]
    queue.remove(0)
    assert queue.current.title == "Two"

    queue.clear()
    assert queue.songs == []
    assert queue.current is None


def test_queue_reorder_preserves_current_song():
    queue = PlaybackQueue()
    original = songs()
    queue.replace(original, 1)

    queue.reorder([original[2], original[1], original[0]])

    assert [song.title for song in queue.songs] == ["Three", "Two", "One"]
    assert queue.current.title == "Two"
    assert queue.current_index == 1


def test_engine_appends_songs_without_replacing_current_queue():
    engine = PlayerEngine()
    original = songs()
    engine.queue.replace(original[:2], 1)

    added = engine.enqueue_songs([original[2]])

    assert added == 1
    assert [song.title for song in engine.queue.songs] == [
        "One",
        "Two",
        "Three",
    ]
    assert engine.current_song.title == "Two"
    engine.deleteLater()


def test_player_time_is_formatted_for_display():
    assert format_milliseconds(0) == "0:00"
    assert format_milliseconds(65_999) == "1:05"
    assert format_milliseconds(3_665_000) == "61:05"


def test_media_library_parses_tag_track_numbers():
    assert _tag_number("02/14") == 2
    assert _tag_number("7") == 7
    assert _tag_number("") == 0


def test_missing_audio_file_is_reported(tmp_path):
    app = QApplication.instance() or QApplication([])
    engine = PlayerEngine()
    errors = []
    engine.error_occurred.connect(errors.append)

    loaded = engine.set_queue(
        [Song(title="Missing", path=str(tmp_path / "missing.flac"))]
    )

    assert loaded is False
    assert errors and "nicht gefunden" in errors[0]
    engine.stop()
    engine.deleteLater()
    app.processEvents()


def test_missing_first_file_is_skipped_when_queue_has_a_valid_file(tmp_path):
    app = QApplication.instance() or QApplication([])
    existing = tmp_path / "existing.flac"
    existing.write_bytes(b"not-a-real-audio-file")
    engine = PlayerEngine()
    errors = []
    engine.error_occurred.connect(errors.append)

    loaded = engine.set_queue(
        [
            Song(title="Missing", path=str(tmp_path / "missing.flac")),
            Song(title="Existing", path=str(existing)),
        ],
        autoplay=False,
    )

    assert loaded is True
    assert engine.current_song.title == "Existing"
    assert errors and "nicht gefunden" in errors[0]
    engine.stop()
    engine.deleteLater()
    app.processEvents()


def test_player_bar_exposes_basic_controls(monkeypatch):
    class EmptySettings:
        def __init__(self, *_args):
            self.values = {}

        def value(self, key, default=None):
            return self.values.get(key, default)

        def setValue(self, key, value):
            self.values[key] = value

    monkeypatch.setattr(
        "musictagstudio.player.widget.QSettings",
        EmptySettings,
    )
    app = QApplication.instance() or QApplication([])
    bar = PlayerBar()

    assert bar.previous_button.toolTip() == "Vorheriger Titel"
    assert bar.play_button.toolTip() == "Wiedergabe/Pause"
    assert bar.next_button.toolTip() == "Nächster Titel"
    assert bar.shuffle_button.toolTip() == "Zufallswiedergabe: Aus"
    assert bar.repeat_button.toolTip() == "Wiederholen: Aus"
    assert bar.queue_button.toolTip() == "Warteschlange anzeigen"
    assert bar.mute_button.toolTip() in {"Stummschalten", "Ton einschalten"}
    assert bar.volume_slider.value() == 70

    was_muted = bar.engine.audio_output.isMuted()
    bar.engine.toggle_mute()
    assert bar.engine.audio_output.isMuted() is not was_muted
    # Knöpfe nutzen jetzt Icons statt Emoji-Text; der Zustand steckt im Tooltip.
    assert not bar.mute_button.icon().isNull()
    now_muted = bar.engine.audio_output.isMuted()
    assert bar.mute_button.toolTip() == (
        "Ton einschalten" if now_muted else "Stummschalten"
    )
    bar.close()
    bar.deleteLater()
    app.processEvents()


def test_queue_dialog_has_one_row_per_song_and_all_actions():
    app = QApplication.instance() or QApplication([])
    engine = PlayerEngine()
    engine.queue.replace(songs(), 0)
    dialog = QueueDialog(engine)

    assert dialog.list.count() == 3
    assert dialog.list.item(0).text().startswith("▶ 01. One")
    assert [
        dialog.play_button.text(),
        dialog.next_button.text(),
        dialog.remove_button.text(),
        dialog.clear_button.text(),
    ] == [
        "Jetzt abspielen",
        "Als Nächstes",
        "Aus Warteschlange entfernen",
        "Warteschlange leeren",
    ]
    dialog.close()
    dialog.deleteLater()
    engine.deleteLater()
    app.processEvents()
