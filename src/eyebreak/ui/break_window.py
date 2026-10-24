import sys
import tkinter as tk
from typing import Callable

from ..scheduler import ReminderKind
from ..windows import IS_WINDOWS, get_foreground_monitor_rect


class BreakWindow:
    def __init__(
        self,
        root: tk.Tk,
        kind: ReminderKind,
        duration: float,
        always_on_top: bool,
        on_start: Callable[[], None],
        on_snooze: Callable[[], None],
        on_skip: Callable[[], None],
    ) -> None:
        self.root = root
        self.kind = kind
        self.duration = max(1.0, float(duration))
        self.remaining = self.duration
        self.on_start = on_start
        self.on_snooze = on_snooze
        self.on_skip = on_skip
        self._after_id = None

        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.title("EyeBreak")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", bool(always_on_top))
        self.window.configure(bg="#0f172a")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.on_snooze)

        self.frame = tk.Frame(self.window, bg="#0f172a", padx=20, pady=16)
        self.frame.pack(fill="both", expand=True)

        if kind == ReminderKind.EYE:
            self.title_text = "Eye break - 20-20-20"
            self.body_text = "Look at an object about 20 feet (6 m) away."
        else:
            self.title_text = "Movement break"
            self.body_text = "Stand up, stretch, or move for a moment."

        tk.Label(
            self.frame,
            text=self.title_text,
            font=("Segoe UI", 11, "bold"),
            fg="#e5e7eb",
            bg="#0f172a",
        ).pack(anchor="w")
        tk.Label(
            self.frame,
            text=self.body_text,
            font=("Segoe UI", 9),
            fg="#cbd5e1",
            bg="#0f172a",
            wraplength=300,
            justify="left",
        ).pack(anchor="w", pady=(4, 12))

        self.canvas = tk.Canvas(
            self.frame,
            width=280,
            height=8,
            bg="#1e293b",
            highlightthickness=0,
        )
        self.canvas.pack(fill="x")
        self._bar = self.canvas.create_rectangle(0, 0, 0, 8, fill="#38bdf8", width=0)

        self.timer_label = tk.Label(
            self.frame,
            text="00:20",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0f172a",
        )
        self.timer_label.pack(anchor="e", pady=(6, 12))

        self.buttons = tk.Frame(self.frame, bg="#0f172a")
        self.buttons.pack(fill="x")
        self.start_btn = tk.Button(
            self.buttons,
            text="Start break",
            command=self._start,
            font=("Segoe UI", 9),
            bg="#38bdf8",
            fg="#0f172a",
            relief="flat",
            padx=12,
            pady=4,
        )
        self.start_btn.pack(side="left")
        tk.Button(
            self.buttons,
            text="Remind me later",
            command=self.on_snooze,
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#e5e7eb",
            relief="flat",
            padx=10,
            pady=4,
        ).pack(side="left", padx=6)
        tk.Button(
            self.buttons,
            text="Skip",
            command=self.on_skip,
            font=("Segoe UI", 9),
            bg="#1e293b",
            fg="#e5e7eb",
            relief="flat",
            padx=10,
            pady=4,
        ).pack(side="left")

        self._position()
        self._tick()

    def _position(self) -> None:
        self.window.update_idletasks()
        width = self.window.winfo_reqwidth()
        height = self.window.winfo_reqheight()

        mon_rect = get_foreground_monitor_rect()
        if mon_rect is not None:
            x = mon_rect.right - width - 16
            y = mon_rect.bottom - height - 56
        else:
            screen_w = self.window.winfo_screenwidth()
            screen_h = self.window.winfo_screenheight()
            x = screen_w - width - 16
            y = screen_h - height - 56

        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def _format(self, seconds: float) -> str:
        total = max(0, int(round(seconds)))
        minutes, secs = divmod(total, 60)
        return f"{minutes:02d}:{secs:02d}"

    def _tick(self) -> None:
        self._after_id = self.window.after(250, self._tick)

    def set_countdown(self, remaining: float) -> None:
        self.remaining = max(0.0, float(remaining))
        ratio = self.remaining / self.duration if self.duration > 0 else 0.0
        width = max(0, int(280 * ratio))
        self.canvas.coords(self._bar, 0, 0, width, 8)
        self.timer_label.configure(text=self._format(self.remaining))
        if self.remaining <= 0:
            if self._after_id:
                try:
                    self.window.after_cancel(self._after_id)
                except Exception:
                    pass
                self._after_id = None

    def show(self) -> None:
        self._position()
        self.window.deiconify()
        self.window.attributes("-topmost", True)
        self.window.lift()
        if IS_WINDOWS:
            try:
                import ctypes
                hwnd = self.window.winfo_id()
                # HWND_TOPMOST = -1, SWP_NOMOVE = 0x2, SWP_NOSIZE = 0x1, SWP_SHOWWINDOW = 0x40, SWP_NOACTIVATE = 0x10
                ctypes.windll.user32.SetWindowPos(
                    hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0040 | 0x0010
                )
            except Exception:
                pass

    def hide(self) -> None:
        if self._after_id:
            try:
                self.window.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        try:
            self.window.withdraw()
        except Exception:
            pass

    def _start(self) -> None:
        self.on_start()


def create_break_window(
    root: tk.Tk,
    kind: ReminderKind,
    duration: float,
    always_on_top: bool,
    on_start: Callable[[], None],
    on_snooze: Callable[[], None],
    on_skip: Callable[[], None],
) -> BreakWindow:
    return BreakWindow(root, kind, duration, always_on_top, on_start, on_snooze, on_skip)
