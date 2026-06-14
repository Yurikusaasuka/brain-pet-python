"""Daily statistics tracking: persistence, midnight reset, 30-second update hook."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Optional

from .constants import ALL_REGION_IDS
from .state_config import BRAIN_STATES

# Chinese display name + bar colour for each region
REGION_DISPLAY: dict[str, tuple[str, str]] = {
    'pfc_left':   ('前额叶',   '#3498DB'),
    'pfc_right':  ('前额叶',   '#3498DB'),
    'parietal':   ('顶叶',     '#17A589'),
    'temporal':   ('颞叶',     '#D68910'),
    'occipital':  ('枕叶',     '#CA6F1E'),
    'cerebellum': ('小脑',     '#27AE60'),
    'limbic':     ('边缘叶',   '#C0392B'),
    'broca':      ('布洛卡区', '#1ABC9C'),
    'brainstem':  ('脑干',     '#922B21'),
}


def _today() -> str:
    return date.today().isoformat()


def empty_stats(date_str: Optional[str] = None) -> dict:
    return {
        'date': date_str or _today(),
        'first_activation_time': datetime.now().strftime('%H:%M'),
        'state_minutes': {sid: 0.0 for sid in BRAIN_STATES},
        'region_intensity_sum': {rid: 0.0 for rid in ALL_REGION_IDS},
        'longest_focus_minutes': 0.0,
        'total_focus_minutes': 0.0,
        'window_switches': 0,
        'pomodoro_count': 0,
    }


def check_midnight_reset(settings: dict) -> bool:
    """
    If date changed, archive the current day to history (keep last 7) and reset.
    Returns True if a reset happened.
    """
    today = _today()
    ds = settings.get('daily_stats')
    if not isinstance(ds, dict) or ds.get('date') != today:
        if isinstance(ds, dict) and ds.get('date'):
            history = settings.get('history')
            if not isinstance(history, list):
                history = []
            history.append(deepcopy(ds))
            settings['history'] = history[-7:]
        settings['daily_stats'] = empty_stats(today)
        return True
    return False


def update_30s(
    settings: dict,
    state_id: str,
    intensities: dict,          # {region_id: float}  — active regions this interval
    switches_30s: int = 0,
    focus_streak_min: float = 0.0,
) -> None:
    """Called every 30 seconds from the main thread to accumulate today's stats."""
    check_midnight_reset(settings)
    ds = settings['daily_stats']

    # State time (each call = 0.5 minutes)
    sm = ds.setdefault('state_minutes', {})
    sm[state_id] = sm.get(state_id, 0.0) + 0.5

    # Region exposure (intensity × 0.5 minutes)
    ri = ds.setdefault('region_intensity_sum', {})
    for rid, intensity in intensities.items():
        if intensity > 0.01:
            ri[rid] = ri.get(rid, 0.0) + intensity * 0.5

    # App switches
    ds['window_switches'] = ds.get('window_switches', 0) + switches_30s

    # Focus streaks
    if state_id in ('DEEP_FOCUS', 'FLOW_STATE', 'FOCUS_STREAK'):
        ds['total_focus_minutes'] = ds.get('total_focus_minutes', 0.0) + 0.5
        if focus_streak_min > ds.get('longest_focus_minutes', 0.0):
            ds['longest_focus_minutes'] = focus_streak_min
