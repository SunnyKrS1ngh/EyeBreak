"""Pure, clock-injectable break scheduling.

The scheduler owns all timing decisions.  It never touches Tk, the Windows
registry, or notifications, which keeps it deterministic and easy to test.

Timing is based on a monotonic clock.  Remaining time is stored as a duration
rather than an absolute wall-clock deadline, so pausing freezes progress and
system clock changes cannot make reminders fire early or late.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable


class ReminderKind(str, Enum):
    EYE = "eye"
    MOVEMENT = "movement"


@dataclass(frozen=True)
class ReminderConfig:
    enabled: bool
    interval_seconds: float
    duration_seconds: float

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")


@dataclass(frozen=True)
class ScheduleSnapshot:
    """A read-only view of one reminder, suitable for the UI."""

    kind: ReminderKind
    enabled: bool
    paused: bool
    status: str  # "idle" | "due" | "in_break"
    pending: bool
    seconds_until_prompt: float | None
    break_remaining: float | None
    interval_seconds: float
    duration_seconds: float


@dataclass(frozen=True)
class PromptDue:
    kind: ReminderKind
    was_pending: bool = False


@dataclass(frozen=True)
class BreakFinished:
    kind: ReminderKind


Event = PromptDue | BreakFinished


@dataclass
class _Schedule:
    config: ReminderConfig
    remaining: float
    status: str = "idle"
    pending: bool = False
    break_remaining: float = 0.0
    kind_paused: bool = False  # paused independently of the global pause


class Scheduler:
    """Independent eye and movement reminder timers.

    ``tick`` advances time and returns events.  A reminder only emits
    ``PromptDue`` once: while it remains due, further ticks are silent until
    the application calls :meth:`snooze`, :meth:`skip`, or
    :meth:`start_break`.  This is what prevents notification storms.
    """

    def __init__(
        self,
        *,
        eye: ReminderConfig,
        movement: ReminderConfig,
        snooze_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if snooze_seconds <= 0:
            raise ValueError("snooze_seconds must be positive")
        self._clock = clock
        self._snooze_seconds = float(snooze_seconds)
        self._last_tick = float(clock())
        self._paused = False
        self._schedules: dict[ReminderKind, _Schedule] = {
            ReminderKind.EYE: _Schedule(eye, float(eye.interval_seconds)),
            ReminderKind.MOVEMENT: _Schedule(
                movement, float(movement.interval_seconds)
            ),
        }

    # ------------------------------------------------------------------ state
    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def snooze_seconds(self) -> float:
        return self._snooze_seconds

    def snapshot(self, kind: ReminderKind) -> ScheduleSnapshot:
        schedule = self._schedules[kind]
        status = schedule.status
        if schedule.config.enabled and status == "in_break":
            break_remaining: float | None = max(0.0, schedule.break_remaining)
            until_prompt: float | None = None
        elif status == "due":
            break_remaining = None
            until_prompt = 0.0
        else:
            break_remaining = None
            until_prompt = max(0.0, schedule.remaining)
        return ScheduleSnapshot(
            kind=kind,
            enabled=schedule.config.enabled,
            paused=self._paused,
            status=status,
            pending=schedule.pending,
            seconds_until_prompt=until_prompt,
            break_remaining=break_remaining,
            interval_seconds=schedule.config.interval_seconds,
            duration_seconds=schedule.config.duration_seconds,
        )

    def snapshots(self) -> tuple[ScheduleSnapshot, ...]:
        return tuple(self.snapshot(kind) for kind in ReminderKind)

    # ---------------------------------------------------------------- actions
    def pause(self) -> None:
        if not self._paused:
            self._paused = True
            # Do not count time spent paused, even if no tick occurred.
            self._last_tick = float(self._clock())

    def resume(self) -> None:
        if self._paused:
            self._paused = False
            self._last_tick = float(self._clock())

    def snooze(self, kind: ReminderKind) -> None:
        """Postpone only this reminder by the configured snooze duration."""
        schedule = self._schedules[kind]
        if not schedule.config.enabled:
            return
        schedule.status = "idle"
        schedule.pending = False
        schedule.break_remaining = 0.0
        schedule.remaining = self._snooze_seconds

    def skip(self, kind: ReminderKind) -> None:
        """Dismiss this reminder and start a fresh interval for it."""
        schedule = self._schedules[kind]
        schedule.status = "idle"
        schedule.pending = False
        schedule.break_remaining = 0.0
        schedule.remaining = float(schedule.config.interval_seconds)

    def start_break(self, kind: ReminderKind) -> bool:
        """Begin the countdown for this reminder.

        Returns ``False`` when the reminder is disabled.
        """
        schedule = self._schedules[kind]
        if not schedule.config.enabled:
            return False
        schedule.status = "in_break"
        schedule.pending = False
        schedule.remaining = 0.0
        schedule.break_remaining = float(schedule.config.duration_seconds)
        return True

    def defer(self, kind: ReminderKind) -> None:
        """Mark a due reminder as pending without notifying.

        Used when the UI must hide a prompt (for example on pause or when a
        full-screen application takes over).  The next unsuppressed tick emits
        a single pending prompt.
        """
        schedule = self._schedules[kind]
        if schedule.status == "due":
            schedule.pending = True

    def pause_kind(self, kind: ReminderKind) -> None:
        """Freeze the idle countdown for one reminder without affecting the other."""
        self._schedules[kind].kind_paused = True

    def resume_kind(self, kind: ReminderKind) -> None:
        """Unfreeze a previously kind-paused reminder."""
        self._schedules[kind].kind_paused = False

    def is_due(self, kind: ReminderKind) -> bool:
        return self._schedules[kind].status == "due"

    def enable(self, kind: ReminderKind, enabled: bool) -> None:
        """Enable or disable one reminder, resetting it when re-enabled."""
        schedule = self._schedules[kind]
        if schedule.config.enabled == enabled:
            return
        schedule.config = ReminderConfig(
            enabled=enabled,
            interval_seconds=schedule.config.interval_seconds,
            duration_seconds=schedule.config.duration_seconds,
        )
        schedule.status = "idle"
        schedule.pending = False
        schedule.break_remaining = 0.0
        schedule.remaining = float(schedule.config.interval_seconds)

    def reconfigure(
        self,
        *,
        eye: ReminderConfig,
        movement: ReminderConfig,
        snooze_seconds: float,
    ) -> None:
        """Apply new settings while preserving sensible in-flight state."""
        if snooze_seconds <= 0:
            raise ValueError("snooze_seconds must be positive")
        self._snooze_seconds = float(snooze_seconds)

        for kind, config in (
            (ReminderKind.EYE, eye),
            (ReminderKind.MOVEMENT, movement),
        ):
            schedule = self._schedules[kind]
            old = schedule.config
            schedule.config = config

            if not config.enabled:
                schedule.status = "idle"
                schedule.pending = False
                schedule.break_remaining = 0.0
                schedule.remaining = float(config.interval_seconds)
            elif not old.enabled:
                # Newly enabled: start a complete interval.
                schedule.status = "idle"
                schedule.pending = False
                schedule.remaining = float(config.interval_seconds)
            elif (
                config.interval_seconds != old.interval_seconds
                and schedule.status == "idle"
            ):
                # Changing an interval deliberately starts a fresh cycle.
                schedule.remaining = float(config.interval_seconds)
            # A due prompt or active break keeps its current state; the new
            # interval/duration applies from the next cycle.

    # ------------------------------------------------------------------- tick
    def tick(self, *, suppress: bool = False, max_step: float | None = None) -> list[Event]:
        """Advance all schedules to the current clock time.

        ``suppress`` turns due prompts into silent pending reminders (used for
        full-screen games).  ``max_step`` clamps a single elapsed gap, which
        the application uses after sleep/resume to avoid a burst of reminders.

        Events are returned in eye-then-movement order.
        """
        now = float(self._clock())
        elapsed = now - self._last_tick
        self._last_tick = now

        if elapsed < 0:
            # A monotonic clock should never move backwards, but never let a
            # bad clock injection add time.
            elapsed = 0.0
        was_clamped = False
        gap = elapsed
        if max_step is not None and elapsed > max_step:
            elapsed = max(0.0, max_step)
            was_clamped = True

        if self._paused:
            return []

        events: list[Event] = []
        for kind in ReminderKind:
            schedule = self._schedules[kind]
            if not schedule.config.enabled:
                continue

            if schedule.status == "in_break":
                schedule.break_remaining -= elapsed
                if schedule.break_remaining <= 0.0:
                    schedule.break_remaining = 0.0
                    schedule.status = "idle"
                    schedule.pending = False
                    schedule.kind_paused = False  # always unfreeze when a break ends
                    schedule.remaining = float(schedule.config.interval_seconds)
                    events.append(BreakFinished(kind))
                continue

            if schedule.status == "due":
                if suppress or schedule.kind_paused:
                    schedule.pending = True
                elif schedule.pending:
                    schedule.pending = False
                    events.append(PromptDue(kind, was_pending=True))
                continue

            # Idle: count down to the next prompt — skip if kind-paused.
            if schedule.kind_paused:
                continue
            if was_clamped and gap > schedule.remaining:
                # After sleep/resume, a large gap that would have crossed zero
                # should produce at most one prompt per schedule.
                schedule.remaining = 0.0
                schedule.status = "due"
                if suppress:
                    schedule.pending = True
                else:
                    events.append(PromptDue(kind))
                continue
            schedule.remaining -= elapsed
            if schedule.remaining <= 0.0:
                schedule.remaining = 0.0
                schedule.status = "due"
                if suppress:
                    schedule.pending = True
                else:
                    events.append(PromptDue(kind))

        return events


def configs_from_seconds(
    *,
    eye_enabled: bool,
    eye_interval: float,
    eye_duration: float,
    movement_enabled: bool,
    movement_interval: float,
    movement_duration: float,
) -> tuple[ReminderConfig, ReminderConfig]:
    return (
        ReminderConfig(eye_enabled, eye_interval, eye_duration),
        ReminderConfig(movement_enabled, movement_interval, movement_duration),
    )


def total_remaining(snapshots: Iterable[ScheduleSnapshot]) -> float:
    """Convenience helper used by tests/diagnostics."""
    return sum(
        snapshot.seconds_until_prompt or 0.0
        for snapshot in snapshots
        if snapshot.enabled and snapshot.seconds_until_prompt is not None
    )
