# EyeBreak

I couldn't find any suitable apps for EyeBreak online, most of them had a lot of bloatware just for a simple task, so I decided to make my own.

If you are a non-tech person: Just open the dist/EyeBreak/EyeBreak.exe file and the app will open.

Description: 
A lightweight, quiet Windows break reminder for 20-20-20 eye breaks and periodic movement breaks. Runs in the system tray, keeps scheduling while minimized, and avoids popping over full-screen games by deferring reminders until it is safe to show them.

## Requirements

- Windows 10/11
- Python 3.11+
- No administrator privileges required
- The app does not inject into other processes, capture keystrokes, or record activity

## Setup (with uv)

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. Do **not** use `pip`, `venv`, or Conda.

```powershell
# Clone or open the repository
cd C:\path\to\eyebreak

# Sync dependencies (creates .venv and installs runtime + dev deps)
uv sync
```

## Development

```powershell
# Run tests
uv run pytest

# Run the app from source
uv run eyebreak

# Run minimized (useful for autostart testing)
uv run python -m eyebreak --minimized
```

## Launch

- **From source:** `uv run eyebreak`
- **System tray:** The app lives in the tray. Use the tray menu to show the dashboard, pause/resume, take a break now, change settings, or quit.
- **Dashboard:** Shows time until the next eye and movement break, and lets you pause/resume or trigger a break immediately.
- **Break window:** A small, topmost prompt asks you to look away (eye break) or move/stretch (movement break). Choose **Start break**, **Remind me later** (snooze), or **Skip**.
- **Close behavior:** If *Close to system tray* is enabled (default), closing the dashboard hides it to the tray. Disable it to quit when closing the dashboard window.

## Configuration

Settings are stored in:

```
%APPDATA%\EyeBreak\config.json
```

Defaults:

| Setting | Default | Notes |
| --- | --- | --- |
| Eye break enabled | On | 20-20-20 style reminder |
| Eye interval | 20 min | Configurable 1-180 min |
| Eye break duration | 20 s | Configurable 5-120 s |
| Movement break enabled | On | Stand/stretch/move |
| Movement interval | 60 min | Configurable 5-360 min |
| Movement break duration | 5 min | Configurable 30s-30 min |
| Snooze duration | 5 min | Configurable 1-60 min |
| Full-screen detection | On | Best-effort; see limitations |
| Start automatically with Windows | Off | Per-user `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, no admin |
| Close to system tray | On | Dashboard close hides to tray |
| Show notifications | On | Uses Windows tray balloon notifications |
| Keep break window on top | On | Does not steal focus |

The app validates and clamps values on load/save. If a config file is missing or malformed, defaults are used and an invalid file is moved to `config.json.corrupt-<timestamp>` next to it.

Logs are written to:

```
%LOCALAPPDATA%\EyeBreak\eyebreak.log
```

## Gaming / full-screen behavior

- **Best-effort detection:** When the foreground window covers its monitor, reminders are suppressed and marked pending.
- **Deferred safely:** If a break is due while in full-screen, no intrusive window is shown. As soon as you leave full-screen, the pending reminder is shown once.
- **No burst on resume:** Large gaps (e.g. sleep/resume) are clamped so at most one prompt per schedule can fire.
- **Disable anytime:** Turn off *Full-screen detection* in settings if it causes issues.
- **Limitations:** Exclusive-fullscreen games can sometimes report different foreground windows; borderless windows not covering the full monitor won't be treated as full-screen; UAC/secure desktops, some overlays, or multi-monitor edge cases may not be detected. The app never injects into processes, hooks input, or captures activity.

## Building a standalone Windows executable

Once the source works (`uv run pytest` passes and `uv run eyebreak` runs correctly), you can build a single-file/windowed executable with [PyInstaller](https://pyinstaller.org/).

```powershell
# Build the standalone Windows app using the configured spec file
uv run pyinstaller EyeBreak.spec --noconfirm
```

### Running the built app

The build output is located at:
```
dist\EyeBreak\EyeBreak.exe
```

- Simply double-click **`EyeBreak.exe`** (or run `.\dist\EyeBreak\EyeBreak.exe` from PowerShell/cmd).
- The entire `dist\EyeBreak\` folder contains everything the app needs to run on any 64-bit Windows machine (no Python installation required).
- The app launches silently into the system tray (notification area near your taskbar clock). Click the tray icon to open the dashboard or right-click for options.

## Troubleshooting

- **Tray icon missing:** Some shells take a moment to initialize the notification area. Try reopening the app or restarting Windows Explorer.
- **Notifications don't appear:** Focus Assist / Do Not Disturb can suppress balloon notifications. Try enabling *Show notifications* and checking Windows notification settings for the app.
- **False full-screen suppression:** Disable *Full-screen detection* in Settings. Borderless games that don't fill the entire monitor are a common case.
- **Second instance won't open:** Only one instance is allowed; it will focus/notify that EyeBreak is already running in the tray.
- **Settings not saving:** Check write permissions to `%APPDATA%\EyeBreak\`. Corrupted files are quarantined automatically and defaults are restored.
- **High DPI:** Tkinter respects Windows DPI in most setups; if scaling looks off, use Windows display scaling as normal.
- **Still getting reminders in-game:** The check is best-effort. If detection fails for a specific game, disable detection for that session or rely on *Pause* from the tray.

## Safety & privacy

- All data stays local. No network requests, no telemetry, no cloud services.
- No keystroke logging, no screenshots, no process injection.
- Runs with normal user privileges only.
