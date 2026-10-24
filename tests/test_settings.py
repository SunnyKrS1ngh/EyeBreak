from pathlib import Path

from eyebreak import settings


def test_load_missing_returns_defaults(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    s = settings.load_settings(path)
    assert s.eye.enabled is True
    assert s.eye.interval_minutes == 20
    assert s.eye.duration_seconds == 20
    assert s.movement.enabled is True
    assert s.movement.interval_minutes == 60
    assert s.movement.duration_seconds == 300
    assert s.snooze_minutes == 5


def test_malformed_json_quarantined_and_defaults_returned(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{ not json", encoding="utf-8")
    s = settings.load_settings(path)
    assert s.eye.interval_minutes == 20
    assert not path.exists()
    assert any(p.name.startswith("config.json.corrupt") for p in tmp_path.iterdir())


def test_invalid_values_clamped(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    raw = {
        "eye": {"enabled": True, "interval_minutes": 0, "duration_seconds": 1},
        "movement": {"enabled": False, "interval_minutes": 9999, "duration_seconds": 5},
        "snooze_minutes": 100,
    }
    import json

    path.write_text(json.dumps(raw), encoding="utf-8")
    s = settings.load_settings(path)
    assert s.eye.interval_minutes == 1
    assert s.eye.duration_seconds == 5
    assert s.movement.enabled is False
    assert s.movement.interval_minutes == 360
    assert s.movement.duration_seconds == 30
    assert s.snooze_minutes == 60


def test_save_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    s = settings.AppSettings()
    s.eye.interval_minutes = 25
    s.movement.duration_seconds = 240
    settings.save_settings(s, path)
    loaded = settings.load_settings(path)
    assert loaded.eye.interval_minutes == 25
    assert loaded.movement.duration_seconds == 240


def test_unknown_keys_ignored(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    import json

    path.write_text(
        json.dumps({"eye": {"interval_minutes": 15}, "unknown": 123, "version": 1}),
        encoding="utf-8",
    )
    s = settings.load_settings(path)
    assert s.eye.interval_minutes == 15
    assert s.movement.interval_minutes == 60
