import time

from eyebreak import scheduler
from eyebreak.scheduler import PromptDue, ReminderConfig, ReminderKind


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def make_scheduler(clock: FakeClock, snooze: float = 300.0) -> scheduler.Scheduler:
    eye = ReminderConfig(True, 1200.0, 20.0)
    movement = ReminderConfig(True, 3600.0, 300.0)
    return scheduler.Scheduler(eye=eye, movement=movement, snooze_seconds=snooze, clock=clock)


def test_fires_at_configured_interval() -> None:
    clock = FakeClock()
    s = make_scheduler(clock)
    events = s.tick()
    assert events == []
    clock.advance(1199.0)
    events = s.tick()
    assert events == []
    clock.advance(1.0)
    events = s.tick()
    kinds = [e.kind for e in events if isinstance(e, PromptDue)]
    assert ReminderKind.EYE in kinds


def test_eye_and_movement_independent() -> None:
    clock = FakeClock()
    s = make_scheduler(clock)
    clock.advance(3600.0)
    events = s.tick()
    kinds = {e.kind for e in events if isinstance(e, PromptDue)}
    assert kinds == {ReminderKind.EYE, ReminderKind.MOVEMENT}


def test_snooze_sets_only_that_reminder() -> None:
    clock = FakeClock()
    s = make_scheduler(clock)
    clock.advance(1200.0)
    events = s.tick()
    assert any(isinstance(e, PromptDue) and e.kind == ReminderKind.EYE for e in events)
    s.snooze(ReminderKind.EYE)
    # Movement should still be far away
    snap_m = s.snapshot(ReminderKind.MOVEMENT)
    assert snap_m.seconds_until_prompt is not None
    assert snap_m.seconds_until_prompt > 2000
    # Snoozed eye should fire in 300s
    clock.advance(299.0)
    events = s.tick()
    assert events == []
    clock.advance(1.0)
    events = s.tick()
    assert any(isinstance(e, PromptDue) and e.kind == ReminderKind.EYE for e in events)


def test_skip_does_not_immediately_re_notify() -> None:
    clock = FakeClock()
    s = make_scheduler(clock)
    clock.advance(1200.0)
    s.tick()
    s.skip(ReminderKind.EYE)
    events = s.tick()
    assert events == []
    clock.advance(1199.0)
    events = s.tick()
    assert events == []
    clock.advance(1.0)
    events = s.tick()
    assert any(isinstance(e, PromptDue) and e.kind == ReminderKind.EYE for e in events)


def test_pause_and_resume_preserve_time() -> None:
    clock = FakeClock()
    s = make_scheduler(clock)
    clock.advance(600.0)
    s.tick()
    s.pause()
    clock.advance(1000.0)
    events = s.tick()
    assert events == []
    s.resume()
    clock.advance(599.0)
    events = s.tick()
    assert events == []
    clock.advance(1.0)
    events = s.tick()
    assert any(isinstance(e, PromptDue) and e.kind == ReminderKind.EYE for e in events)


def test_sleep_gap_no_burst() -> None:
    clock = FakeClock()
    s = make_scheduler(clock)
    # Sleep for 4 hours
    clock.advance(14400.0)
    events = s.tick(max_step=300.0)
    kinds = [e.kind for e in events if isinstance(e, PromptDue)]
    # Only the first schedule(s) due at that moment should fire, not a burst
    assert kinds
    assert len(kinds) <= 2
    # Running ticks again should not immediately re-fire the same due reminder
    events = s.tick(max_step=300.0)
    assert all(not isinstance(e, PromptDue) for e in events)


def test_fullscreen_suppression_pending_emitted_once() -> None:
    clock = FakeClock()
    s = make_scheduler(clock)
    clock.advance(1200.0)
    events = s.tick(suppress=True)
    assert events == []
    snap = s.snapshot(ReminderKind.EYE)
    assert snap.status == "due"
    assert snap.pending is True
    # Still suppressed
    clock.advance(60.0)
    events = s.tick(suppress=True)
    assert events == []
    # Unsuppressed -> emit once
    events = s.tick(suppress=False)
    assert any(isinstance(e, PromptDue) and e.kind == ReminderKind.EYE for e in events)
    events = s.tick(suppress=False)
    assert events == []


def test_no_repeated_prompt_while_due() -> None:
    clock = FakeClock()
    s = make_scheduler(clock)
    clock.advance(1200.0)
    events = s.tick()
    assert any(isinstance(e, PromptDue) for e in events)
    events = s.tick()
    assert events == []


def test_invalid_settings_handled_safely() -> None:
    # The scheduler validates in __init__
    try:
        ReminderConfig(True, -1.0, 20.0)
        assert False
    except ValueError:
        pass
    try:
        ReminderConfig(True, 1200.0, 0.0)
        assert False
    except ValueError:
        pass
