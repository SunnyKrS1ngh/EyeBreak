from eyebreak import windows


def test_rect_covers_monitor_exact() -> None:
    m = windows.Rect(0, 0, 1920, 1080)
    w = windows.Rect(0, 0, 1920, 1080)
    assert windows.rect_covers_monitor(w, m) is True


def test_rect_covers_monitor_with_small_tolerance() -> None:
    m = windows.Rect(0, 0, 1920, 1080)
    w = windows.Rect(-1, -1, 1920, 1080)
    assert windows.rect_covers_monitor(w, m, tolerance=2) is True


def test_rect_not_fullscreen() -> None:
    m = windows.Rect(0, 0, 1920, 1080)
    w = windows.Rect(0, 0, 1600, 900)
    assert windows.rect_covers_monitor(w, m) is False


def test_shell_window_class() -> None:
    assert windows.is_shell_window_class("Progman") is True
    assert windows.is_shell_window_class("Shell_TrayWnd") is True
    assert windows.is_shell_window_class("Notepad") is False
