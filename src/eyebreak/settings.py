"""User settings and safe JSON persistence.

Configuration lives in ``%APPDATA%\\EyeBreak\\config.json``.  Loading is
deliberately forgiving: missing files use defaults, malformed files are moved
aside, and individual invalid values are clamped or replaced.  A broken config
must never prevent the app from starting.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

APP_NAME = "EyeBreak"
CONFIG_VERSION = 1

# Validation bounds.  Durations are stored in seconds; intervals are minutes.
EYE_INTERVAL_RANGE = (1, 180)
EYE_DURATION_RANGE = (5, 120)
MOVEMENT_INTERVAL_RANGE = (5, 360)
MOVEMENT_DURATION_RANGE = (30, 1800)
SNOOZE_RANGE = (1, 60)

log = logging.getLogger(__name__)


def _roaming_root() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Roaming"


def _local_root() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Local"


def config_dir() -> Path:
    override = os.environ.get("EYEBREAK_CONFIG_DIR")
    if override:
        return Path(override)
    return _roaming_root() / APP_NAME


def default_config_path() -> Path:
    return config_dir() / "config.json"


def log_dir() -> Path:
    return _local_root() / APP_NAME


@dataclass
class EyeSettings:
    enabled: bool = True
    interval_minutes: int = 20
    duration_seconds: int = 20


@dataclass
class MovementSettings:
    enabled: bool = True
    interval_minutes: int = 60
    duration_seconds: int = 300


@dataclass
class AppSettings:
    eye: EyeSettings = field(default_factory=EyeSettings)
    movement: MovementSettings = field(default_factory=MovementSettings)
    snooze_minutes: int = 5
    fullscreen_detection: bool = True
    autostart: bool = False
    close_to_tray: bool = True
    show_notifications: bool = True
    always_on_top: bool = True
    version: int = CONFIG_VERSION

    def validated(self) -> "AppSettings":
        return validate_settings(self)


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    return default


def _clamp(value: Any, default: int, bounds: tuple[int, int]) -> int:
    low, high = bounds
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    return max(low, min(high, int(round(number))))


def validate_settings(settings: AppSettings) -> AppSettings:
    """Return a validated copy with every field inside safe bounds."""
    eye = settings.eye
    movement = settings.movement
    return replace(
        settings,
        eye=EyeSettings(
            enabled=_coerce_bool(eye.enabled, True),
            interval_minutes=_clamp(
                eye.interval_minutes, 20, EYE_INTERVAL_RANGE
            ),
            duration_seconds=_clamp(
                eye.duration_seconds, 20, EYE_DURATION_RANGE
            ),
        ),
        movement=MovementSettings(
            enabled=_coerce_bool(movement.enabled, True),
            interval_minutes=_clamp(
                movement.interval_minutes, 60, MOVEMENT_INTERVAL_RANGE
            ),
            duration_seconds=_clamp(
                movement.duration_seconds, 300, MOVEMENT_DURATION_RANGE
            ),
        ),
        snooze_minutes=_clamp(settings.snooze_minutes, 5, SNOOZE_RANGE),
        fullscreen_detection=_coerce_bool(settings.fullscreen_detection, True),
        autostart=_coerce_bool(settings.autostart, False),
        close_to_tray=_coerce_bool(settings.close_to_tray, True),
        show_notifications=_coerce_bool(settings.show_notifications, True),
        always_on_top=_coerce_bool(settings.always_on_top, True),
        version=CONFIG_VERSION,
    )


def settings_from_dict(raw: dict[str, Any]) -> AppSettings:
    """Merge a user-supplied mapping with defaults, ignoring bad fields."""
    defaults = AppSettings()
    eye_raw = raw.get("eye")
    movement_raw = raw.get("movement")
    if not isinstance(eye_raw, dict):
        eye_raw = {}
    if not isinstance(movement_raw, dict):
        movement_raw = {}

    eye = EyeSettings(
        enabled=_coerce_bool(
            eye_raw.get("enabled", defaults.eye.enabled), defaults.eye.enabled
        ),
        interval_minutes=_clamp(
            eye_raw.get("interval_minutes", defaults.eye.interval_minutes),
            defaults.eye.interval_minutes,
            EYE_INTERVAL_RANGE,
        ),
        duration_seconds=_clamp(
            eye_raw.get("duration_seconds", defaults.eye.duration_seconds),
            defaults.eye.duration_seconds,
            EYE_DURATION_RANGE,
        ),
    )
    movement = MovementSettings(
        enabled=_coerce_bool(
            movement_raw.get("enabled", defaults.movement.enabled),
            defaults.movement.enabled,
        ),
        interval_minutes=_clamp(
            movement_raw.get(
                "interval_minutes", defaults.movement.interval_minutes
            ),
            defaults.movement.interval_minutes,
            MOVEMENT_INTERVAL_RANGE,
        ),
        duration_seconds=_clamp(
            movement_raw.get(
                "duration_seconds", defaults.movement.duration_seconds
            ),
            defaults.movement.duration_seconds,
            MOVEMENT_DURATION_RANGE,
        ),
    )

    settings = AppSettings(
        eye=eye,
        movement=movement,
        snooze_minutes=_clamp(
            raw.get("snooze_minutes", defaults.snooze_minutes),
            defaults.snooze_minutes,
            SNOOZE_RANGE,
        ),
        fullscreen_detection=_coerce_bool(
            raw.get("fullscreen_detection", defaults.fullscreen_detection),
            defaults.fullscreen_detection,
        ),
        autostart=_coerce_bool(
            raw.get("autostart", defaults.autostart), defaults.autostart
        ),
        close_to_tray=_coerce_bool(
            raw.get("close_to_tray", defaults.close_to_tray),
            defaults.close_to_tray,
        ),
        show_notifications=_coerce_bool(
            raw.get("show_notifications", defaults.show_notifications),
            defaults.show_notifications,
        ),
        always_on_top=_coerce_bool(
            raw.get("always_on_top", defaults.always_on_top),
            defaults.always_on_top,
        ),
        version=CONFIG_VERSION,
    )
    return validate_settings(settings)


def _quarantine(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        path.replace(target)
        log.warning("Moved invalid settings file to %s", target)
    except OSError:
        log.exception("Could not move invalid settings file %s", path)


def load_settings(path: Path | None = None) -> AppSettings:
    """Load settings, recovering to defaults on any problem."""
    path = Path(path) if path is not None else default_config_path()
    if not path.exists():
        return AppSettings()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        log.exception("Could not read settings from %s", path)
        if path.exists():
            _quarantine(path)
        return AppSettings()

    if not isinstance(raw, dict):
        log.warning("Settings root is not an object in %s", path)
        _quarantine(path)
        return AppSettings()

    version = raw.get("version", CONFIG_VERSION)
    if not isinstance(version, int) or isinstance(version, bool):
        log.warning("Invalid settings version %r; using defaults", version)
    elif version != CONFIG_VERSION:
        log.info(
            "Loading settings version %s (current is %s)",
            version,
            CONFIG_VERSION,
        )
    try:
        return settings_from_dict(raw)
    except Exception:
        # Defensive: settings_from_dict is written not to raise, but a bad
        # config must never prevent startup.
        log.exception("Unexpected error validating settings")
        _quarantine(path)
        return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> Path:
    """Atomically write validated settings and return the target path."""
    path = Path(path) if path is not None else default_config_path()
    validated = settings.validated()
    data = asdict(validated)
    data["version"] = CONFIG_VERSION
    path.parent.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(data, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                log.debug("Could not remove temporary settings file", exc_info=True)
    return path
