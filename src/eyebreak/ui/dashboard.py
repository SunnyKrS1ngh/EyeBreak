"""Dashboard and settings dialog."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from ..scheduler import ReminderKind, Scheduler
from ..settings import AppSettings


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, settings: AppSettings, on_save: Callable[[AppSettings], None]) -> None:
        super().__init__(parent)
        self.title("EyeBreak Settings")
        self.configure(bg="#0f172a")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.settings = settings
        self.on_save = on_save

        pad = {"padx": 12, "pady": 6}
        frame = tk.Frame(self, bg="#0f172a")
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Eye break", font=("Segoe UI", 10, "bold"), fg="#e5e7eb", bg="#0f172a").grid(row=0, column=0, sticky="w", **pad)
        tk.Label(frame, text="Movement break", font=("Segoe UI", 10, "bold"), fg="#e5e7eb", bg="#0f172a").grid(row=0, column=1, sticky="w", **pad)

        self.eye_enabled = tk.BooleanVar(value=settings.eye.enabled)
        self.movement_enabled = tk.BooleanVar(value=settings.movement.enabled)
        tk.Checkbutton(frame, text="Enabled", variable=self.eye_enabled, bg="#0f172a", fg="#e5e7eb", selectcolor="#1e293b", activebackground="#0f172a").grid(row=1, column=0, sticky="w", padx=12)
        tk.Checkbutton(frame, text="Enabled", variable=self.movement_enabled, bg="#0f172a", fg="#e5e7eb", selectcolor="#1e293b", activebackground="#0f172a").grid(row=1, column=1, sticky="w", padx=12)

        self.eye_interval = tk.IntVar(value=settings.eye.interval_minutes)
        self.eye_duration = tk.IntVar(value=settings.eye.duration_seconds)
        self.movement_interval = tk.IntVar(value=settings.movement.interval_minutes)
        self.movement_duration = tk.IntVar(value=settings.movement.duration_seconds)

        def add_row(r: int, c: int, label: str, var: tk.IntVar) -> None:
            tk.Label(frame, text=label, fg="#cbd5e1", bg="#0f172a").grid(row=r, column=c, sticky="w", padx=12)
            spin = tk.Spinbox(frame, from_=1, to=360, textvariable=var, width=6)
            spin.grid(row=r, column=c + 1, sticky="w")

        add_row(2, 0, "Interval (min)", self.eye_interval)
        add_row(3, 0, "Duration (s)", self.eye_duration)
        add_row(2, 1, "Interval (min)", self.movement_interval)
        add_row(3, 1, "Duration (s)", self.movement_duration)

        tk.Label(frame, text="General", font=("Segoe UI", 10, "bold"), fg="#e5e7eb", bg="#0f172a").grid(row=4, column=0, sticky="w", **pad)

        self.snooze = tk.IntVar(value=settings.snooze_minutes)
        self.fullscreen = tk.BooleanVar(value=settings.fullscreen_detection)
        self.autostart = tk.BooleanVar(value=settings.autostart)
        self.close_tray = tk.BooleanVar(value=settings.close_to_tray)
        self.notify = tk.BooleanVar(value=settings.show_notifications)
        self.ontop = tk.BooleanVar(value=settings.always_on_top)

        g = 5
        def check(r: int, text: str, var: tk.BooleanVar) -> None:
            tk.Checkbutton(frame, text=text, variable=var, bg="#0f172a", fg="#e5e7eb", selectcolor="#1e293b", activebackground="#0f172a").grid(row=r, column=0, columnspan=2, sticky="w", padx=12)

        tk.Label(frame, text="Snooze (min)", fg="#cbd5e1", bg="#0f172a").grid(row=g, column=0, sticky="w", padx=12)
        tk.Spinbox(frame, from_=1, to=60, textvariable=self.snooze, width=6).grid(row=g, column=1, sticky="w")
        check(6, "Enable full-screen detection", self.fullscreen)
        check(7, "Start automatically with Windows", self.autostart)
        check(8, "Close to system tray", self.close_tray)
        check(9, "Show notifications", self.notify)
        check(10, "Keep break window on top", self.ontop)

        btns = tk.Frame(frame, bg="#0f172a")
        btns.grid(row=11, column=0, columnspan=2, sticky="e", padx=12, pady=12)
        tk.Button(btns, text="Cancel", command=self.destroy, relief="flat", padx=10, pady=4).pack(side="right")
        tk.Button(btns, text="Save", command=self._save, bg="#38bdf8", fg="#0f172a", relief="flat", padx=12, pady=4).pack(side="right", padx=6)

        self.grab_release()
        self.focus_set()

    def _save(self) -> None:
        new_settings = AppSettings(
            eye=__import__("eyebreak.settings", fromlist=["EyeSettings"]).EyeSettings(
                enabled=self.eye_enabled.get(),
                interval_minutes=self.eye_interval.get(),
                duration_seconds=self.eye_duration.get(),
            ),
            movement=__import__("eyebreak.settings", fromlist=["MovementSettings"]).MovementSettings(
                enabled=self.movement_enabled.get(),
                interval_minutes=self.movement_interval.get(),
                duration_seconds=self.movement_duration.get(),
            ),
            snooze_minutes=self.snooze.get(),
            fullscreen_detection=self.fullscreen.get(),
            autostart=self.autostart.get(),
            close_to_tray=self.close_tray.get(),
            show_notifications=self.notify.get(),
            always_on_top=self.ontop.get(),
        )
        validated = __import__("eyebreak.settings", fromlist=["validate_settings"]).validate_settings(new_settings)
        self.on_save(validated)
        self.destroy()


class Dashboard(tk.Toplevel):
    def __init__(self, root: tk.Tk, scheduler: Scheduler, on_pause_toggle: Callable[[], None], on_take: Callable[[ReminderKind], None], on_settings: Callable[[], None]) -> None:
        super().__init__(root)
        self.title("EyeBreak Dashboard")
        self.configure(bg="#0f172a")
        self.geometry("420x220")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self.scheduler = scheduler
        self.on_pause_toggle = on_pause_toggle
        self.on_take = on_take
        self.on_settings = on_settings

        frame = tk.Frame(self, bg="#0f172a", padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="EyeBreak", font=("Segoe UI", 12, "bold"), fg="#e5e7eb", bg="#0f172a").pack(anchor="w")
        tk.Label(frame, text="Next breaks", font=("Segoe UI", 9), fg="#94a3b8", bg="#0f172a").pack(anchor="w")

        cards = tk.Frame(frame, bg="#0f172a")
        cards.pack(fill="x", pady=(12, 12))

        self.eye_label = tk.Label(cards, text="Eye: --:--", font=("Segoe UI", 10), fg="#e5e7eb", bg="#0f172a")
        self.movement_label = tk.Label(cards, text="Movement: --:--", font=("Segoe UI", 10), fg="#e5e7eb", bg="#0f172a")
        self.eye_label.pack(anchor="w")
        self.movement_label.pack(anchor="w", pady=(4, 0))

        self.status_label = tk.Label(frame, text="", font=("Segoe UI", 8), fg="#38bdf8", bg="#0f172a")
        self.status_label.pack(anchor="w")

        buttons = tk.Frame(frame, bg="#0f172a")
        buttons.pack(fill="x", side="bottom")
        self.pause_btn = tk.Button(buttons, text="Pause", command=self.on_pause_toggle, relief="flat", padx=10, pady=4)
        self.pause_btn.pack(side="left")
        tk.Button(buttons, text="Take eye break now", command=lambda: self.on_take(ReminderKind.EYE), relief="flat", padx=10, pady=4).pack(side="left", padx=6)
        tk.Button(buttons, text="Take movement break now", command=lambda: self.on_take(ReminderKind.MOVEMENT), relief="flat", padx=10, pady=4).pack(side="left")
        tk.Button(buttons, text="Settings", command=self.on_settings, relief="flat", padx=10, pady=4).pack(side="right")

        self._tick()

    def _format(self, seconds: float | None) -> str:
        if seconds is None:
            return "--:--"
        total = max(0, int(round(seconds)))
        minutes, secs = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _tick(self) -> None:
        snap_eye = self.scheduler.snapshot(ReminderKind.EYE)
        snap_move = self.scheduler.snapshot(ReminderKind.MOVEMENT)

        if snap_eye.enabled and snap_eye.status == "due":
            self.eye_label.configure(text="Eye: Due now")
        elif snap_eye.enabled and snap_eye.status == "in_break":
            self.eye_label.configure(text=f"Eye: In break ({self._format(snap_eye.break_remaining)})")
        elif snap_eye.enabled:
            self.eye_label.configure(text=f"Eye: {self._format(snap_eye.seconds_until_prompt)}")
        else:
            self.eye_label.configure(text="Eye: Disabled")

        if snap_move.enabled and snap_move.status == "due":
            self.movement_label.configure(text="Movement: Due now")
        elif snap_move.enabled and snap_move.status == "in_break":
            self.movement_label.configure(text=f"Movement: In break ({self._format(snap_move.break_remaining)})")
        elif snap_move.enabled:
            self.movement_label.configure(text=f"Movement: {self._format(snap_move.seconds_until_prompt)}")
        else:
            self.movement_label.configure(text="Movement: Disabled")

        if self.scheduler.paused:
            self.pause_btn.configure(text="Resume")
            self.status_label.configure(text="Reminders paused")
        else:
            self.pause_btn.configure(text="Pause")
            self.status_label.configure(text="")

        self.after(1000, self._tick)

    def show(self) -> None:
        self.deiconify()
        self.lift()


def create_dashboard(root: tk.Tk, scheduler: Scheduler, on_pause_toggle: Callable[[], None], on_take: Callable[[ReminderKind], None], on_settings: Callable[[], None]) -> Dashboard:
    return Dashboard(root, scheduler, on_pause_toggle, on_take, on_settings)
