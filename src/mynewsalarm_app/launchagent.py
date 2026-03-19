from __future__ import annotations

import plistlib
from pathlib import Path

from .config import BUNDLE_ID, validate_alarm_time


def launchagents_dir() -> Path:
    base = Path.home() / "Library" / "LaunchAgents"
    base.mkdir(parents=True, exist_ok=True)
    return base


def label() -> str:
    return BUNDLE_ID


def plist_filename() -> str:
    return f"{label()}.plist"


def render_plist(*, app_path: Path, hour: int, minute: int, log_path: Path) -> dict:
    # Use /usr/bin/open so we can run the packaged .app at a specific time.
    # LaunchAgent will run the app, pass --run-once, then the app exits.
    return {
        "Label": label(),
        "ProgramArguments": [
            "/usr/bin/open",
            "-a",
            str(app_path),
            "--args",
            "--run-once",
        ],
        "StartCalendarInterval": {"Hour": int(hour), "Minute": int(minute)},
        "RunAtLoad": False,
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
        "EnvironmentVariables": {
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
        },
    }


def write_plist(dest: Path, plist_obj: dict) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        plistlib.dump(plist_obj, f)


def install_launchagent(*, alarm_time: str, app_path: Path, log_path: Path) -> Path:
    hour, minute = validate_alarm_time(alarm_time)
    dest = launchagents_dir() / plist_filename()
    plist_obj = render_plist(app_path=app_path, hour=hour, minute=minute, log_path=log_path)
    write_plist(dest, plist_obj)
    return dest


def uninstall_launchagent() -> Path:
    dest = launchagents_dir() / plist_filename()
    if dest.exists():
        dest.unlink()
    return dest
