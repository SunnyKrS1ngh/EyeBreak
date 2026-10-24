"""Small, dependency-free Windows integration helpers.

Only documented Win32 APIs are used: foreground-window inspection for
best-effort full-screen detection, the per-user Run registry key for autostart,
and a named mutex for single-instance behaviour.  Nothing is injected into
other processes and no input is captured.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_VALUE = "EyeBreak"
ERROR_ALREADY_EXISTS = 183
MONITOR_DEFAULTTOPRIMARY = 1
MONITOR_DEFAULTTONEAREST = 2
SPI_GETWORKAREA = 0x0030
DWMWA_CLOAKED = 14

_SHELL_CLASS_NAMES = frozenset(
    {
        "Progman",
        "WorkerW",
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "Windows.UI.Core.CoreWindow",
        "XamlExplorerHostIslandWindow",
        "ApplicationManager_DesktopShellWindow",
        "MultitaskingViewFrame",
        "ForegroundStaging",
    }
)


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def rect_covers_monitor(
    window: Rect, monitor: Rect, tolerance: int = 2
) -> bool:
    """Return True when a window rectangle covers its monitor.

    The tolerance absorbs small invisible borders and DPI rounding.  Pure
    function so the geometry decision is testable without Windows windows.
    """
    return (
        window.left <= monitor.left + tolerance
        and window.top <= monitor.top + tolerance
        and window.right >= monitor.right - tolerance
        and window.bottom >= monitor.bottom - tolerance
    )


def is_shell_window_class(class_name: str) -> bool:
    return class_name in _SHELL_CLASS_NAMES


if IS_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetShellWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.GetMonitorInfoW.argtypes = [
        wintypes.HMONITOR,
        ctypes.POINTER(MONITORINFO),
    ]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.GetClassNameW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.SystemParametersInfoW.argtypes = [
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        wintypes.UINT,
    ]
    user32.SystemParametersInfoW.restype = wintypes.BOOL

    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        dwmapi.DwmGetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
    except OSError:
        dwmapi = None
else:  # pragma: no cover - the application targets Windows
    user32 = None
    kernel32 = None
    shell32 = None
    dwmapi = None


def _window_class_name(hwnd: int) -> str:
    assert user32 is not None
    buffer = ctypes.create_unicode_buffer(256)
    length = user32.GetClassNameW(hwnd, buffer, len(buffer))
    if length <= 0:
        return ""
    return buffer.value


def _is_cloaked(hwnd: int) -> bool:
    if dwmapi is None:
        return False
    assert user32 is not None
    cloaked = wintypes.DWORD(0)
    result = dwmapi.DwmGetWindowAttribute(
        hwnd,
        DWMWA_CLOAKED,
        ctypes.byref(cloaked),
        ctypes.sizeof(cloaked),
    )
    return result == 0 and cloaked.value != 0


def is_foreground_fullscreen(own_pid: int | None = None) -> bool:
    """Best-effort check whether the foreground window fills its monitor.

    Returns False on any Win32 error.  This intentionally favours not hiding
    reminders: a false negative shows a prompt, while a false positive would
    postpone it.

    Limitations: exclusive-mode games may report a different foreground
    window; borderless windows that do not cover the full monitor are treated
    as normal windows; taskbar overlays and some UAC/secure desktops are not
    visible to this process.
    """
    if not IS_WINDOWS or user32 is None:
        return False

    own_pid = os.getpid() if own_pid is None else own_pid
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        if user32.IsWindowVisible(hwnd) == 0 or user32.IsIconic(hwnd) != 0:
            return False
        if hwnd == user32.GetShellWindow():
            return False

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own_pid:
            return False

        class_name = _window_class_name(hwnd)
        if is_shell_window_class(class_name):
            return False
        if _is_cloaked(hwnd):
            return False

        window_rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(window_rect)):
            return False

        monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        if not monitor:
            return False
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False

        return rect_covers_monitor(
            Rect(
                window_rect.left,
                window_rect.top,
                window_rect.right,
                window_rect.bottom,
            ),
            Rect(
                info.rcMonitor.left,
                info.rcMonitor.top,
                info.rcMonitor.right,
                info.rcMonitor.bottom,
            ),
        )
    except (OSError, ValueError):
        log.debug("Full-screen detection failed", exc_info=True)
        return False


def get_primary_work_area() -> Rect | None:
    """Return the primary monitor work area in physical pixels, if available."""
    if not IS_WINDOWS or user32 is None:
        return None
    rect = RECT()
    if not user32.SystemParametersInfoW(
        SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
    ):
        return None
    return Rect(rect.left, rect.top, rect.right, rect.bottom)


# --------------------------------------------------------------------- autostart
def autostart_command() -> str:
    """Build the command stored in the per-user Run key."""
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable)
        return f'"{executable}" --minimized'

    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.exists():
        executable = pythonw
    return f'"{executable}" -m eyebreak --minimized'


def is_autostart_enabled() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE
        ) as key:
            value, _kind = winreg.QueryValueEx(key, AUTOSTART_VALUE)
        return bool(str(value).strip())
    except FileNotFoundError:
        return False
    except OSError:
        log.exception("Could not read autostart registry value")
        return False


def set_autostart(enabled: bool) -> None:
    """Enable or disable login startup for the current user (no admin)."""
    if not IS_WINDOWS:
        raise RuntimeError("Autostart is only supported on Windows")
    import winreg

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        if enabled:
            winreg.SetValueEx(
                key,
                AUTOSTART_VALUE,
                0,
                winreg.REG_SZ,
                autostart_command(),
            )
        else:
            try:
                winreg.DeleteValue(key, AUTOSTART_VALUE)
            except FileNotFoundError:
                pass


# ------------------------------------------------------------------ single instance
class SingleInstance:
    """Named mutex preventing two schedulers from running at once."""

    def __init__(self, name: str = "Local\\EyeBreak.SingleInstance.v1") -> None:
        self.already_running = False
        self._handle = None
        if not IS_WINDOWS or kernel32 is None:
            return

        kernel32.CreateMutexW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateMutexW(None, False, name)
        last_error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(last_error)
        self._handle = handle
        self.already_running = last_error == ERROR_ALREADY_EXISTS

    def close(self) -> None:
        if self._handle and kernel32 is not None:
            kernel32.CloseHandle(self._handle)
            self._handle = None


def show_message(title: str, message: str, *, error: bool = False) -> None:
    """Show a native MessageBox, used for startup problems only."""
    if not IS_WINDOWS:
        print(f"{title}: {message}")
        return
    flags = 0x00000010 if error else 0x00000040  # MB_ICONERROR / MB_ICONINFORMATION
    user32.MessageBoxW(None, message, title, flags)  # type: ignore[union-attr]


def set_app_user_model_id(app_id: str = "EyeBreak.App") -> None:
    """Give the process a stable taskbar/notification identity."""
    if not IS_WINDOWS or shell32 is None:
        return
    try:
        shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except OSError:
        log.debug("Could not set AppUserModelID", exc_info=True)
