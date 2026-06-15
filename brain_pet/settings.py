from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

from .constants import APP_CATEGORIES


def _data_dir() -> Path:
    """Return a writable, platform-appropriate directory for app data."""
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home()))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    d = base / 'brain-pet'
    d.mkdir(parents=True, exist_ok=True)
    return d


SETTINGS_PATH = _data_dir() / 'settings.json'

DEFAULT_SETTINGS: dict = {
    # window
    "brain_size": "M",
    "x": None,
    "y": None,
    "opacity": 0.98,
    # display
    "bubble_enabled": True,
    "animation_enabled": True,
    # state persistence (manual override; None = auto)
    "manual_state": None,
    # thresholds
    "focus_threshold": 20,
    "rest_threshold": 5,
    "overload_window_count": 10,
    # feature toggles
    "video_question_enabled": True,
    "flow_alert_enabled": True,
    "late_night_reminder_enabled": True,
    # auto-hide toggles
    "hide_on_game": False,
    "hide_on_fullscreen_video": False,
    # editable work app list
    "work_apps": list(APP_CATEGORIES["WORK"]),
    # pomodoro configuration
    "pomodoro": {
        "work_minutes": 25,
        "work_tolerance": 2,
        "break_minutes": 5,
        "break_tolerance": 1,
        "streak_threshold": 3,
    },
    # daily_stats: initialized by daily_stats.check_midnight_reset() on first run
    "daily_stats": None,
    # history: list of archived daily_stats dicts, last 7 days
    "history": [],
}


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return deepcopy(DEFAULT_SETTINGS)
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULT_SETTINGS)
    merged = deepcopy(DEFAULT_SETTINGS)
    for key in merged:
        if key in data:
            merged[key] = data[key]
    # Merge nested pomodoro dict so partial saves don't lose defaults
    if isinstance(data.get('pomodoro'), dict):
        for k, v in data['pomodoro'].items():
            merged['pomodoro'][k] = v
    return merged


def save_settings(settings: dict) -> None:
    merged = deepcopy(DEFAULT_SETTINGS)
    for key in merged:
        if key in settings:
            merged[key] = settings[key]
    # Merge pomodoro sub-dict
    if isinstance(settings.get('pomodoro'), dict):
        merged['pomodoro'] = {**merged['pomodoro'], **settings['pomodoro']}
    SETTINGS_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
