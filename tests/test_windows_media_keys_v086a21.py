import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from musictagstudio.player.windows_media_keys import (
    APPCOMMAND_MEDIA_NEXTTRACK,
    APPCOMMAND_MEDIA_PLAY_PAUSE,
    HOTKEY_NEXT,
    HOTKEY_PLAY_PAUSE,
    HOTKEY_PREVIOUS,
    HOTKEY_STOP,
    HOTKEYS,
    WindowsMediaKeyController,
    app_command_from_lparam,
)


class EngineStub:
    def __init__(self):
        self.calls = []

    def toggle(self):
        self.calls.append("toggle")

    def next(self):
        self.calls.append("next")

    def previous(self):
        self.calls.append("previous")

    def stop(self):
        self.calls.append("stop")


def test_media_key_commands_dispatch_to_player_engine():
    engine = EngineStub()
    controller = WindowsMediaKeyController(engine)

    assert controller.handle_hotkey_id(HOTKEY_PLAY_PAUSE)
    assert controller.handle_hotkey_id(HOTKEY_NEXT)
    assert controller.handle_hotkey_id(HOTKEY_PREVIOUS)
    assert controller.handle_hotkey_id(HOTKEY_STOP)
    assert controller.handle_hotkey_id(999999) is False
    assert engine.calls == ["toggle", "next", "previous", "stop"]


def test_windows_app_command_is_decoded_and_dispatched():
    engine = EngineStub()
    controller = WindowsMediaKeyController(engine)
    lparam = APPCOMMAND_MEDIA_PLAY_PAUSE << 16

    assert app_command_from_lparam(lparam) == APPCOMMAND_MEDIA_PLAY_PAUSE
    assert controller.handle_app_command(APPCOMMAND_MEDIA_NEXTTRACK)
    assert engine.calls == ["next"]


def test_hotkey_lifecycle_releases_every_successful_registration(monkeypatch):
    QApplication.instance() or QApplication([])
    engine = EngineStub()
    controller = WindowsMediaKeyController(engine)
    registered = []
    unregistered = []
    monkeypatch.setattr(
        "musictagstudio.player.windows_media_keys.sys.platform", "win32"
    )
    monkeypatch.setattr(
        controller,
        "_register",
        lambda hotkey_id, virtual_key:
            registered.append((hotkey_id, virtual_key)) or True,
    )
    monkeypatch.setattr(
        controller,
        "_unregister",
        unregistered.append,
    )

    assert controller.start(12345)
    controller.stop()

    assert registered == list(HOTKEYS.items())
    assert set(unregistered) == set(HOTKEYS)
