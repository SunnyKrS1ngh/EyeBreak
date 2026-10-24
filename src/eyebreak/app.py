"""Application controller and entry point."""
from __future__ import annotations

import logging
import sys
import tkinter as tk
from typing import Any

from . import __version__
from .icon import create_icon
from .scheduler import BreakFinished, Event, PromptDue, ReminderConfig, ReminderKind, Scheduler, configs_from_seconds
from .sound import BRUH_SOUND, SHABASH_SOUND, WELL_DONE_SOUND, AlertSound, play_sound_once
from .settings import AppSettings, load_settings, log_dir, save_settings
from .ui.break_window import BreakWindow
from .ui.dashboard import Dashboard
from .ui.tray import Tray
from .windows import SingleInstance, is_autostart_enabled, is_foreground_fullscreen, set_app_user_model_id, set_autostart, show_message

log = logging.getLogger(__name__)

MAX_SLEEP_STEP = 300.0
TICK_INTERVAL_MS = 1000


class EyeBreakApp:
    def __init__(self, root: tk.Tk, settings: AppSettings, start_minimized: bool = False) -> None:
        self.root = root
        self.settings = settings.validated()
        self.start_minimized = start_minimized
        self.scheduler: Scheduler | None = None
        self.dashboard: Dashboard | None = None
        self.tray: Tray | None = None
        self.break_window: BreakWindow | None = None
        self.current_break_kind: ReminderKind | None = None
        # Tracks the kind for a break window that is actively counting down
        self._break_window_kind: ReminderKind | None = None
        self._alert_sound: AlertSound = AlertSound(self.root, repeat_ms=5000)

        self.root.title("EyeBreak")
        self.root.geometry("1x1+0+0")
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._setup_scheduler()
        self._setup_tray()
        self._setup_dashboard()
        self._tick()

    def _setup_scheduler(self) -> None:
        eye_c, move_c = configs_from_seconds(
            eye_enabled=self.settings.eye.enabled,
            eye_interval=self.settings.eye.interval_minutes * 60.0,
            eye_duration=float(self.settings.eye.duration_seconds),  # already in seconds
            movement_enabled=self.settings.movement.enabled,
            movement_interval=self.settings.movement.interval_minutes * 60.0,
            movement_duration=float(self.settings.movement.duration_seconds),  # already in seconds
        )
        self.scheduler = Scheduler(
            eye=eye_c,
            movement=move_c,
            snooze_seconds=self.settings.snooze_minutes * 60.0,
        )

    def _setup_tray(self) -> None:
        icon_image = create_icon()
        self.tray = Tray(
            icon_image=icon_image,
            on_show=self._show_dashboard,
            on_pause_toggle=self._toggle_pause,
            on_take_eye=lambda: self._take_now(ReminderKind.EYE),
            on_take_movement=lambda: self._take_now(ReminderKind.MOVEMENT),
            on_settings=self._open_settings,
            on_quit=self._quit,
            is_paused=self._is_paused,
        )
        self.tray.start()

    def _setup_dashboard(self) -> None:
        assert self.scheduler is not None
        self.dashboard = Dashboard(
            self.root,
            self.scheduler,
            self._toggle_pause,
            self._take_now,
            self._open_settings,
        )
        if not self.start_minimized:
            self.dashboard.show()

    def _tick(self) -> None:
        assert self.scheduler is not None
        suppress = False
        if self.settings.fullscreen_detection:
            suppress = is_foreground_fullscreen()
        try:
            events = self.scheduler.tick(suppress=suppress, max_step=MAX_SLEEP_STEP)
        except Exception:
            log.exception("Scheduler tick failed")
            events = []
        self._handle_events(events)
        # Update break window countdown if active.
        # Use current_break_kind for prompt windows, break_window_kind for
        # in-progress break countdowns (set after Start is pressed).
        tracking_kind = self._break_window_kind or self.current_break_kind
        if self.break_window is not None and tracking_kind is not None:
            snap = self.scheduler.snapshot(tracking_kind)
            if snap.status == "in_break" and snap.break_remaining is not None:
                try:
                    self.break_window.set_countdown(snap.break_remaining)
                    if snap.break_remaining <= 0:
                        try:
                            self.break_window.hide()
                        except Exception:
                            pass
                        self.break_window = None
                        self._break_window_kind = None
                        self.current_break_kind = None
                        # Resume the other timer now that countdown hit zero.
                        if self.scheduler is not None:
                            self.scheduler.resume_kind(self._other_kind(tracking_kind))
                except Exception:
                    pass
            elif snap.status != "in_break" and self._break_window_kind is not None:
                # Break finished via BreakFinished event path; clean up.
                try:
                    self.break_window.hide()
                except Exception:
                    pass
                self.break_window = None
                self._break_window_kind = None
                self.current_break_kind = None
        if self.scheduler.paused and self.tray is not None:
            self.tray.update_menu()
        self.root.after(TICK_INTERVAL_MS, self._tick)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _other_kind(kind: ReminderKind) -> ReminderKind:
        """Return the opposite ReminderKind."""
        return ReminderKind.MOVEMENT if kind == ReminderKind.EYE else ReminderKind.EYE

    def _handle_events(self, events: list[Event]) -> None:
        for event in events:
            if isinstance(event, PromptDue):
                self._show_break_prompt(event.kind)
            elif isinstance(event, BreakFinished):
                log.info("Break finished: %s", event.kind.value)
                # Resume the other timer now that this break is over.
                if self.scheduler is not None:
                    self.scheduler.resume_kind(self._other_kind(event.kind))
                # Play completion sound effect
                if event.kind == ReminderKind.MOVEMENT:
                    play_sound_once(WELL_DONE_SOUND)
                elif event.kind == ReminderKind.EYE:
                    play_sound_once(SHABASH_SOUND)
                # Match against _break_window_kind (active countdown) OR
                # current_break_kind (prompt still showing, edge case).
                active_kind = self._break_window_kind or self.current_break_kind
                if self.break_window is not None and active_kind == event.kind:
                    try:
                        self.break_window.hide()
                    except Exception:
                        pass
                    self.break_window = None
                    self._break_window_kind = None
                    self.current_break_kind = None

    def _break_duration(self, kind: ReminderKind) -> float:
        snap = self.scheduler.snapshot(kind) if self.scheduler else None
        if snap is not None:
            return snap.duration_seconds
        if kind == ReminderKind.EYE:
            return float(self.settings.eye.duration_seconds)
        return float(self.settings.movement.duration_seconds)

    def _show_break_prompt(self, kind: ReminderKind) -> None:
        if self.break_window is not None:
            return
        if self.scheduler is None:
            return
        duration = self._break_duration(kind)
        self.current_break_kind = kind
        self.break_window = BreakWindow(
            self.root,
            kind,
            duration,
            always_on_top=self.settings.always_on_top,
            on_start=self._start_break_from_prompt,
            on_snooze=self._snooze_prompt,
            on_skip=self._skip_prompt,
        )
        self.break_window.show()
        self._notify(kind)
        self._alert_sound.play()  # ring until user acts

    def _notify(self, kind: ReminderKind) -> None:
        if not self.settings.show_notifications or self.tray is None or self.tray.icon is None:
            return
        if kind == ReminderKind.EYE:
            title = "EyeBreak - Eye break"
            message = "Time to look 20 feet away for 20 seconds."
        else:
            title = "EyeBreak - Movement break"
            message = "Time to stand up, stretch, or move."
        try:
            self.tray.icon.notify(message, title)
        except Exception:
            log.debug("Tray notification failed", exc_info=True)

    def _start_break_from_prompt(self) -> None:
        if self.scheduler is None or self.current_break_kind is None:
            return
        self._alert_sound.stop()  # user started the break — silence the alert
        kind = self.current_break_kind
        self.scheduler.start_break(kind)
        # Pause the other timer while this break is active.
        self.scheduler.pause_kind(self._other_kind(kind))
        if self.break_window is not None:
            # Keep window open to show break countdown.
            duration = self._break_duration(kind)
            self.break_window.duration = duration
            self.break_window.remaining = duration
            # Reconfigure buttons to just show a status label.
            for widget in self.break_window.buttons.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass
            import tkinter as tk
            tk.Label(
                self.break_window.buttons,
                text="Take your break...",
                font=("Segoe UI", 9),
                fg="#94a3b8",
                bg="#0f172a",
            ).pack(side="left")
            self.break_window.set_countdown(duration)
        # Store which break is in-progress so _tick can track it.
        self._break_window_kind = kind
        self.current_break_kind = None

    def _snooze_prompt(self) -> None:
        if self.scheduler is None or self.current_break_kind is None:
            return
        self._alert_sound.stop()
        # User snoozed without taking the break — resume the other timer.
        self.scheduler.resume_kind(self._other_kind(self.current_break_kind))
        self.scheduler.snooze(self.current_break_kind)
        self._dismiss_prompt()

    def _skip_prompt(self) -> None:
        if self.scheduler is None or self.current_break_kind is None:
            return
        self._alert_sound.stop()
        # User skipped without taking the break — resume the other timer.
        self.scheduler.resume_kind(self._other_kind(self.current_break_kind))
        self.scheduler.skip(self.current_break_kind)
        self._dismiss_prompt()
        play_sound_once(BRUH_SOUND)

    def _dismiss_prompt(self) -> None:
        self._alert_sound.stop()
        if self.break_window is not None:
            self.break_window.hide()
            self.break_window = None
        self.current_break_kind = None

    def _take_now(self, kind: ReminderKind) -> None:
        if self.scheduler is None:
            return
        if not self.scheduler.start_break(kind):
            return
        # _take_now jumps straight into a break (no prompt stage).
        # Pause the other timer while this break is active.
        self.scheduler.pause_kind(self._other_kind(kind))
        self._break_window_kind = kind
        self.current_break_kind = None
        duration = self._break_duration(kind)
        if self.break_window is not None:
            try:
                self.break_window.hide()
            except Exception:
                pass
        self.break_window = BreakWindow(
            self.root,
            kind,
            duration,
            always_on_top=self.settings.always_on_top,
            on_start=lambda: None,
            on_snooze=lambda: None,
            on_skip=lambda: None,
        )
        # Show break window with countdown; replace buttons with status label.
        for widget in self.break_window.buttons.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass
        import tkinter as tk
        tk.Label(
            self.break_window.buttons,
            text="Take your break...",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0f172a",
        ).pack(side="left")
        self.break_window.set_countdown(duration)
        self.break_window.show()

    def _toggle_pause(self) -> None:
        if self.scheduler is None:
            return
        if self.scheduler.paused:
            self.scheduler.resume()
        else:
            self.scheduler.pause()
        if self.tray is not None:
            self.tray.update_menu()

    def _is_paused(self) -> bool:
        return self.scheduler.paused if self.scheduler else False

    def _show_dashboard(self) -> None:
        if self.dashboard is not None:
            self.dashboard.show()

    def _open_settings(self) -> None:
        from .ui.dashboard import SettingsDialog

        def on_save(new_settings: AppSettings) -> None:
            self._apply_settings(new_settings)

        SettingsDialog(self.root, self.settings, on_save)

    def _apply_settings(self, new_settings: AppSettings) -> None:
        old_autostart = self.settings.autostart
        self.settings = new_settings.validated()
        save_settings(self.settings)

        if self.scheduler is not None:
            eye_c, move_c = configs_from_seconds(
                eye_enabled=self.settings.eye.enabled,
                eye_interval=self.settings.eye.interval_minutes * 60.0,
                eye_duration=float(self.settings.eye.duration_seconds),  # already in seconds
                movement_enabled=self.settings.movement.enabled,
                movement_interval=self.settings.movement.interval_minutes * 60.0,
                movement_duration=float(self.settings.movement.duration_seconds),  # already in seconds
            )
            self.scheduler.reconfigure(
                eye=eye_c,
                movement=move_c,
                snooze_seconds=self.settings.snooze_minutes * 60.0,
            )

        if old_autostart != self.settings.autostart:
            try:
                set_autostart(self.settings.autostart)
            except Exception:
                log.exception("Failed to update autostart")
                show_message("EyeBreak", "Could not update automatic startup.", error=True)

        if self.dashboard is not None:
            self.dashboard.destroy()
        self.dashboard = Dashboard(
            self.root,
            self.scheduler,
            self._toggle_pause,
            self._take_now,
            self._open_settings,
        )
        if self.settings.close_to_tray or not self.start_minimized:
            pass
        if self.tray is not None:
            self.tray.update_menu()

    def _on_close(self) -> None:
        if self.settings.close_to_tray:
            if self.dashboard is not None:
                self.dashboard.withdraw()
        else:
            self._quit()

    def _quit(self) -> None:
        if self.tray is not None:
            self.tray.stop()
        try:
            self.root.quit()
        except Exception:
            pass


def _setup_logging() -> None:
    directory = log_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(directory / "eyebreak.log", encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    start_minimized = "--minimized" in argv
    _setup_logging()
    set_app_user_model_id()
    instance = SingleInstance()
    if instance.already_running:
        show_message("EyeBreak", "EyeBreak is already running in the system tray.")
        return 0

    settings = load_settings()
    if settings.autostart != is_autostart_enabled():
        try:
            set_autostart(settings.autostart)
        except Exception:
            log.debug("Could not sync autostart state", exc_info=True)

    root = tk.Tk()
    try:
        app = EyeBreakApp(root, settings, start_minimized=start_minimized)
        root.mainloop()
    except Exception:
        log.exception("Unhandled application error")
        show_message(
            "EyeBreak",
            "EyeBreak encountered an unexpected error. Check the log in AppData/Local/EyeBreak/.",
            error=True,
        )
        return 1
    finally:
        instance.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
