"""Tray integration."""
from __future__ import annotations

import threading
from typing import Callable

import pystray
from PIL import Image

from ..scheduler import ReminderKind


class Tray:
    def __init__(
        self,
        icon_image: Image.Image,
        on_show: Callable[[], None],
        on_pause_toggle: Callable[[], None],
        on_take_eye: Callable[[], None],
        on_take_movement: Callable[[], None],
        on_settings: Callable[[], None],
        on_quit: Callable[[], None],
        is_paused: Callable[[], bool],
    ) -> None:
        self.icon_image = icon_image
        self.on_show = on_show
        self.on_pause_toggle = on_pause_toggle
        self.on_take_eye = on_take_eye
        self.on_take_movement = on_take_movement
        self.on_settings = on_settings
        self.on_quit = on_quit
        self.is_paused = is_paused
        self.icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def _menu(self) -> pystray.Menu:
        pause_label = "Resume" if self.is_paused() else "Pause"
        return pystray.Menu(
            pystray.MenuItem("Show dashboard", lambda: self.on_show(), default=True),
            pystray.MenuItem(pause_label, lambda: self.on_pause_toggle()),
            pystray.MenuItem("Take eye break now", lambda: self.on_take_eye()),
            pystray.MenuItem("Take movement break now", lambda: self.on_take_movement()),
            pystray.MenuItem("Settings", lambda: self.on_settings()),
            pystray.MenuItem("Quit", lambda: self.on_quit()),
        )

    def start(self) -> None:
        if self.icon is not None:
            return
        self.icon = pystray.Icon("EyeBreak", self.icon_image, "EyeBreak", self._menu())
        self._thread = threading.Thread(target=self.icon.run, name="EyeBreakTray", daemon=True)
        self._thread.start()

    def update_menu(self) -> None:
        if self.icon is not None:
            self.icon.menu = self._menu()
            self.icon.update_menu()

    def stop(self) -> None:
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
        self._thread = None
