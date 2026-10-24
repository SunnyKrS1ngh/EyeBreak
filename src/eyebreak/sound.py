"""Lightweight MP3 playback via the Windows MCI API.

No third-party dependencies: winmm.dll ships with every Windows install.
The public interface is a single :class:`AlertSound` object that:
  - plays the sound immediately on ``play()``
  - replays automatically every *repeat_interval_ms* milliseconds via a
    tkinter ``after`` callback until ``stop()`` is called
  - is safe to call from any tkinter callback
"""

from __future__ import annotations

import ctypes
import itertools
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk

log = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"

# Resolve the bundled sound file.
# When frozen by PyInstaller the package lives under sys._MEIPASS;
# in a normal install it lives next to this source file.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _SOUNDS_DIR = Path(sys._MEIPASS) / "eyebreak" / "sounds"
else:
    _SOUNDS_DIR = Path(__file__).parent / "sounds"

DEFAULT_SOUND = _SOUNDS_DIR / "faah.mp3"

# Unique alias counter so multiple simultaneous open commands don't clash.
_alias_counter = itertools.count(1)


def _mci(command: str) -> bool:
    """Send an MCI string command; return True on success."""
    if not IS_WINDOWS:
        return False
    try:
        result = ctypes.windll.winmm.mciSendStringW(command, None, 0, None)
        if result != 0:
            log.debug("MCI command %r returned error %d", command, result)
            return False
        return True
    except Exception:
        log.debug("MCI command failed: %r", command, exc_info=True)
        return False


def _play_once(path: Path) -> str | None:
    """Open and start playing *path*; return the MCI alias or None on failure."""
    alias = f"eyebreak_alert_{next(_alias_counter)}"
    if _mci(f'open "{path}" type mpegvideo alias {alias}'):
        if _mci(f"play {alias}"):
            return alias
        _mci(f"close {alias}")
    return None


def _close_alias(alias: str) -> None:
    _mci(f"stop {alias}")
    _mci(f"close {alias}")


class AlertSound:
    """Plays an MP3 alert and repeats it every *repeat_ms* milliseconds.

    Typical use::

        sound = AlertSound(root, repeat_ms=5000)
        sound.play()   # called when break prompt appears
        # … user clicks Start break …
        sound.stop()   # silence immediately
    """

    def __init__(
        self,
        root: tk.Misc,
        path: Path = DEFAULT_SOUND,
        repeat_ms: int = 5000,
    ) -> None:
        self._root = root
        self._path = path
        self._repeat_ms = repeat_ms
        self._active = False
        self._after_id: str | None = None
        self._current_alias: str | None = None

    # ------------------------------------------------------------------ public

    def play(self) -> None:
        """Start playing immediately, then repeat every *repeat_ms* ms."""
        if self._active:
            return
        self._active = True
        self._play_once_and_schedule()

    def stop(self) -> None:
        """Stop playback and cancel any pending repeat."""
        self._active = False
        if self._after_id is not None:
            try:
                self._root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._current_alias is not None:
            _close_alias(self._current_alias)
            self._current_alias = None

    # ----------------------------------------------------------------- private

    def _play_once_and_schedule(self) -> None:
        if not self._active:
            return
        # Close the previous alias if still open.
        if self._current_alias is not None:
            _close_alias(self._current_alias)
            self._current_alias = None
        self._current_alias = _play_once(self._path)
        if self._current_alias is None:
            log.debug("AlertSound: playback failed for %s", self._path)
        # Schedule the next repeat regardless of whether this play succeeded.
        self._after_id = self._root.after(self._repeat_ms, self._play_once_and_schedule)
