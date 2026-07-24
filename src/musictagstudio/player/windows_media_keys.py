from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication

from .engine import PlayerEngine


LOGGER = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
WM_APPCOMMAND = 0x0319
MOD_NOREPEAT = 0x4000

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

APPCOMMAND_MEDIA_NEXTTRACK = 11
APPCOMMAND_MEDIA_PREVIOUSTRACK = 12
APPCOMMAND_MEDIA_STOP = 13
APPCOMMAND_MEDIA_PLAY_PAUSE = 14

HOTKEY_PLAY_PAUSE = 0x4D50
HOTKEY_NEXT = 0x4D51
HOTKEY_PREVIOUS = 0x4D52
HOTKEY_STOP = 0x4D53

HOTKEYS = {
    HOTKEY_PLAY_PAUSE: VK_MEDIA_PLAY_PAUSE,
    HOTKEY_NEXT: VK_MEDIA_NEXT_TRACK,
    HOTKEY_PREVIOUS: VK_MEDIA_PREV_TRACK,
    HOTKEY_STOP: VK_MEDIA_STOP,
}


def app_command_from_lparam(lparam: int) -> int:
    return (int(lparam) >> 16) & 0x0FFF


class WindowsMediaKeyController(QAbstractNativeEventFilter):
    def __init__(self, engine: PlayerEngine) -> None:
        super().__init__()
        self.engine = engine
        self.window_handle = 0
        self.registered_ids: set[int] = set()
        self._installed = False

    def start(self, window_handle: int) -> bool:
        if sys.platform != "win32":
            return False
        self.window_handle = int(window_handle)
        app = QApplication.instance()
        if app is not None and not self._installed:
            app.installNativeEventFilter(self)
            self._installed = True
        for hotkey_id, virtual_key in HOTKEYS.items():
            if self._register(hotkey_id, virtual_key):
                self.registered_ids.add(hotkey_id)
            else:
                LOGGER.warning(
                    "Windows-Medientaste konnte nicht registriert werden: "
                    "ID=%s, VK=%s",
                    hotkey_id,
                    virtual_key,
                )
        return bool(self.registered_ids)

    def stop(self) -> None:
        if sys.platform == "win32" and self.window_handle:
            for hotkey_id in tuple(self.registered_ids):
                self._unregister(hotkey_id)
        self.registered_ids.clear()
        app = QApplication.instance()
        if app is not None and self._installed:
            app.removeNativeEventFilter(self)
        self._installed = False
        self.window_handle = 0

    def handle_hotkey_id(self, hotkey_id: int) -> bool:
        actions: dict[int, Callable[[], object]] = {
            HOTKEY_PLAY_PAUSE: self.engine.toggle,
            HOTKEY_NEXT: self.engine.next,
            HOTKEY_PREVIOUS: self.engine.previous,
            HOTKEY_STOP: self.engine.stop,
        }
        action = actions.get(int(hotkey_id))
        if action is None:
            return False
        action()
        return True

    def handle_app_command(self, command: int) -> bool:
        commands = {
            APPCOMMAND_MEDIA_PLAY_PAUSE: HOTKEY_PLAY_PAUSE,
            APPCOMMAND_MEDIA_NEXTTRACK: HOTKEY_NEXT,
            APPCOMMAND_MEDIA_PREVIOUSTRACK: HOTKEY_PREVIOUS,
            APPCOMMAND_MEDIA_STOP: HOTKEY_STOP,
        }
        hotkey_id = commands.get(int(command))
        return hotkey_id is not None and self.handle_hotkey_id(hotkey_id)

    def nativeEventFilter(self, event_type, message):
        if sys.platform != "win32":
            return False, 0
        try:
            address = int(message)
            msg = ctypes.cast(
                address, ctypes.POINTER(wintypes.MSG)
            ).contents
        except (TypeError, ValueError, OSError):
            return False, 0
        if msg.message == WM_HOTKEY:
            return self.handle_hotkey_id(int(msg.wParam)), 0
        if msg.message == WM_APPCOMMAND:
            command = app_command_from_lparam(int(msg.lParam))
            return self.handle_app_command(command), 0
        return False, 0

    def _register(self, hotkey_id: int, virtual_key: int) -> bool:
        return bool(
            ctypes.windll.user32.RegisterHotKey(
                self.window_handle,
                hotkey_id,
                MOD_NOREPEAT,
                virtual_key,
            )
        )

    def _unregister(self, hotkey_id: int) -> None:
        ctypes.windll.user32.UnregisterHotKey(
            self.window_handle,
            hotkey_id,
        )
