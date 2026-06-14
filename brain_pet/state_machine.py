"""State machine: determines current brain state ID from monitor data + manual overrides."""
from __future__ import annotations

import queue
import time
from collections import deque
from datetime import datetime
from typing import Optional

from .constants import THRESHOLDS, MANUAL_STATES, TIME_WINDOWS, ENTERTAINMENT_CATEGORIES
from .state_config import BRAIN_STATES, TIME_OVERLAYS
from .window_monitor import WindowMonitor, MonitorSnapshot

# Work states: switching among these does NOT interrupt the pomodoro work timer.
# Includes meeting/music-work as user-requested "work-adjacent" activities.
_WORK_STATES = frozenset({
    'DEEP_FOCUS', 'NORMAL_WORK', 'CODE_DEBUG', 'WRITING',
    'FOCUS_STREAK', 'FLOW_STATE',
    'MEETING', 'MUSIC_WORK',
})

# Break states: system-idle-based rest (keyboard/mouse inactive).
_BREAK_STATES = frozenset({'SHORT_REST', 'DEEP_AWAY', 'IDLE'})

# Entertainment/distraction states: entering one of these resets the pom work timer.
_DISTRACT_STATES = frozenset({
    'GAMING', 'VIDEO_UNKNOWN', 'VIDEO_DOCUMENTARY', 'VIDEO_ENTERTAINMENT',
    'VIDEO_HORROR', 'SOCIAL_MEDIA', 'DOPAMINE_CRASH',
    'MIXED', 'PROCRASTINATION',
})


# ---------------------------------------------------------------------------
# BrainState – live snapshot consumed by the compositor
# ---------------------------------------------------------------------------

class BrainState:
    """Wraps a state dict and exposes per-region intensity/color after applying anim mult."""

    def __init__(self, state_dict: dict) -> None:
        self._s = state_dict
        self._mult: float = 1.0

    def set_mult(self, mult: float) -> None:
        self._mult = max(0.0, min(1.0, mult))

    def get_intensity(self, region_id: str) -> float:
        region = self._s['regions'].get(region_id)
        if region is None:
            return 0.0
        return region['intensity'] * self._mult

    def get_color(self, region_id: str) -> str:
        region = self._s['regions'].get(region_id)
        if region is None:
            return '#FFFFFF'
        return region.get('color', '#FFFFFF')

    def get_effect(self, region_id: str) -> Optional[str]:
        region = self._s['regions'].get(region_id)
        if region is None:
            return None
        return region.get('effect')

    @property
    def state_dict(self) -> dict:
        return self._s


# ---------------------------------------------------------------------------
# Time overlay helper
# ---------------------------------------------------------------------------

def current_time_overlay() -> dict:
    now_dt = datetime.now()
    h, m = now_dt.hour, now_dt.minute
    tw = TIME_WINDOWS

    if tw['MORNING_START'] <= h < tw['MORNING_END']:
        base = TIME_OVERLAYS['MORNING']
        elapsed_min = (h - 6) * 60 + m
        if elapsed_min < 30:
            ramp = 0.20 + (base['brightness'] - 0.20) * (elapsed_min / 30.0)
            return {**base, 'brightness': round(ramp, 3)}
        return base

    if tw['PEAK_START'] <= h < tw['PEAK_END']:
        return TIME_OVERLAYS['PEAK']
    if tw['AFTERNOON_DIP_START'] <= h < tw['AFTERNOON_DIP_END']:
        return TIME_OVERLAYS['AFTERNOON_DIP']
    if tw['AFTERNOON_START'] <= h < tw['AFTERNOON_END']:
        return TIME_OVERLAYS['AFTERNOON']
    if tw['EVENING_START'] <= h < tw['EVENING_END']:
        return TIME_OVERLAYS['EVENING']
    if tw['NIGHT_EARLY_START'] <= h < tw['NIGHT_EARLY_END']:
        return TIME_OVERLAYS['NIGHT_EARLY']
    if tw['NIGHT_START'] <= h < tw['NIGHT_END']:
        return TIME_OVERLAYS['NIGHT']
    return TIME_OVERLAYS['LATE_NIGHT']


# ---------------------------------------------------------------------------
# StateMachine
# ---------------------------------------------------------------------------

class StateMachine:
    """
    Runs a background WindowMonitor and derives the current state ID each tick.
    All public members are called from the main thread only.
    """

    def __init__(self, settings: dict) -> None:
        self._settings = settings
        self._q: queue.Queue[MonitorSnapshot] = queue.Queue(maxsize=5)
        self._monitor = WindowMonitor(self._q)
        self._snap: Optional[MonitorSnapshot] = None

        # Manual override
        self._manual: Optional[str] = settings.get('manual_state')

        # Video tracking
        self._video_subtype: Optional[str] = None
        self._video_start: Optional[float] = None
        self._pending_video_q: bool = False
        self._video_q_shown: bool = False

        # One-time bubble messages
        self._pending_bubble: Optional[str] = None
        self._session_bubbles_shown: set[str] = set()

        # Procrastination tracking
        self._last_cat: Optional[str] = None
        self._work_entertainment_switches: deque[float] = deque()

        # Active pomodoro phase tracking
        # Phase values: '' | 'WORK' | 'WORK_DONE' | 'REST' | 'REST_DONE'
        self._pom_phase: str = ''
        self._pom_active_work_start: Optional[float] = None   # when current work session started
        self._pom_active_rest_start: Optional[float] = None   # when confirmed rest started
        self._pom_streak: int = 0

        self._prev_state: str = 'IDLE'
        self._focus_start: Optional[float] = None

        # Dopamine crash tracking
        self._crash_triggered: bool = False
        self._dopamine_entered: bool = False

    # ------------------------------------------------------------------
    # Public API (main thread)
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._monitor.start()

    def stop(self) -> None:
        self._monitor.stop()

    def set_manual(self, state_id: Optional[str]) -> None:
        if state_id in MANUAL_STATES or state_id is None:
            self._manual = state_id

    def answer_video(self, subtype: str) -> None:
        """Accept a video subtype code ('DOCUMENTARY', 'ENTERTAINMENT', 'HORROR', 'GAMING')."""
        self._video_subtype = subtype
        self._pending_video_q = False
        self._video_q_shown = True

    def get_pending_bubble(self) -> Optional[str]:
        msg = self._pending_bubble
        self._pending_bubble = None
        return msg

    @property
    def pending_video_question(self) -> bool:
        return self._pending_video_q

    @property
    def last_snap(self) -> Optional[MonitorSnapshot]:
        return self._snap

    @property
    def pomodoro_streak(self) -> int:
        return self._pom_streak

    @property
    def current_focus_minutes(self) -> float:
        if self._focus_start is None:
            return 0.0
        return (time.monotonic() - self._focus_start) / 60.0

    def pop_dopamine_entered(self) -> bool:
        if self._dopamine_entered:
            self._dopamine_entered = False
            return True
        return False

    # ------------------------------------------------------------------
    # Active pomodoro public API
    # ------------------------------------------------------------------

    @property
    def pom_phase(self) -> str:
        """Current pomodoro phase: '' | 'WORK' | 'WORK_DONE' | 'REST' | 'REST_DONE'."""
        return self._pom_phase

    @property
    def pom_work_elapsed_seconds(self) -> float:
        """Seconds elapsed in the current work session (0 if not tracking)."""
        if self._pom_phase not in ('WORK', 'WORK_DONE') or self._pom_active_work_start is None:
            return 0.0
        return time.monotonic() - self._pom_active_work_start

    @property
    def pom_rest_remaining_seconds(self) -> float:
        """Seconds remaining in the rest countdown (0 if not in REST phase)."""
        if self._pom_phase != 'REST' or self._pom_active_rest_start is None:
            return 0.0
        cfg = self._settings.get('pomodoro', {})
        break_secs = cfg.get('break_minutes', 5) * 60.0
        elapsed = time.monotonic() - self._pom_active_rest_start
        return max(0.0, break_secs - elapsed)

    def pom_confirm_break(self) -> None:
        """User confirmed starting the rest break."""
        if self._pom_phase == 'WORK_DONE':
            self._pom_phase = 'REST'
            self._pom_active_rest_start = time.monotonic()

    def pom_confirm_work(self) -> None:
        """User confirmed restarting work after rest."""
        if self._pom_phase == 'REST_DONE':
            self._pom_streak += 1
            ds = self._settings.get('daily_stats')
            if isinstance(ds, dict):
                ds['pomodoro_count'] = ds.get('pomodoro_count', 0) + 1
            self._pending_bubble = '🍅 番茄钟完成！专注力+1'
            self._pom_phase = 'WORK'
            self._pom_active_work_start = time.monotonic()

    def pom_skip_rest(self) -> None:
        """User skipped the rest period."""
        self._pom_phase = 'WORK'
        self._pom_active_work_start = time.monotonic()

    # ------------------------------------------------------------------
    # Main update (called every frame from the UI thread)
    # ------------------------------------------------------------------

    def update(self) -> str:
        # Drain monitor queue — keep only the most recent snapshot
        try:
            while True:
                self._snap = self._q.get_nowait()
        except queue.Empty:
            pass

        state_id = self._compute()

        # Track deep-focus start/end for daily stats
        if state_id in ('DEEP_FOCUS', 'FLOW_STATE', 'FOCUS_STREAK'):
            if self._focus_start is None:
                self._focus_start = time.monotonic()
        else:
            self._focus_start = None

        self._update_pom_phase(state_id)
        self._check_one_time_bubbles(state_id)
        self._prev_state = state_id
        return state_id

    # ------------------------------------------------------------------
    # Core state logic
    # ------------------------------------------------------------------

    def _compute(self) -> str:
        snap = self._snap
        now = time.monotonic()
        settings = self._settings
        hour = datetime.now().hour

        if self._manual is not None and self._manual in BRAIN_STATES:
            return self._manual

        # --- OVERLOAD (highest priority) ---
        if snap is not None:
            sw3 = len([t for t in snap.recent_switches if now - t <= 180.0])
            if (snap.window_count >= settings.get('overload_window_count', THRESHOLDS['OVERLOAD_WINDOWS'])
                    or sw3 >= THRESHOLDS['OVERLOAD_SWITCHES']):
                return 'OVERLOAD'

        # --- FLOW STATE ---
        if (snap is not None
                and snap.has_work_window
                and settings.get('flow_alert_enabled', True)):
            work_cont_min = snap.work_continuous_seconds / 60.0
            if work_cont_min >= THRESHOLDS['FLOW_MINUTES']:
                return 'FLOW_STATE'

        # --- FOCUS_STREAK ---
        pom_cfg = settings.get('pomodoro', {})
        streak_threshold = pom_cfg.get('streak_threshold', 3)
        if snap is not None and self._pom_streak >= streak_threshold:
            work_cont_min = snap.work_continuous_seconds / 60.0
            fthr = settings.get('focus_threshold', THRESHOLDS['FOCUS_MINUTES'])
            if snap.has_work_window and work_cont_min >= fthr:
                return 'FOCUS_STREAK'

        if snap is None:
            return 'IDLE'

        # Track category transitions for procrastination detection
        cat = snap.category
        if cat != self._last_cat:
            prev = self._last_cat
            if ((prev == 'WORK' and cat in ('VIDEO', 'BROWSER_VIDEO', 'SOCIAL', 'GAME'))
                    or (prev in ('VIDEO', 'BROWSER_VIDEO', 'SOCIAL', 'GAME') and cat == 'WORK')):
                self._work_entertainment_switches.append(now)
            self._last_cat = cat

        cutoff = now - THRESHOLDS['PROCRASTINATION_WINDOW_MIN'] * 60.0
        while self._work_entertainment_switches and self._work_entertainment_switches[0] < cutoff:
            self._work_entertainment_switches.popleft()

        # --- PROCRASTINATION ---
        if len(self._work_entertainment_switches) >= THRESHOLDS['PROCRASTINATION_SWITCHES']:
            return 'PROCRASTINATION'

        # --- STRESS: late night + work ---
        if hour < 6 and cat == 'WORK':
            return 'STRESS_HIGH'

        # --- REST (based on system idle time) ---
        idle_min = snap.idle_seconds / 60.0

        if 0 <= hour < 6 and idle_min >= 120.0:
            return 'SLEEPING'

        if idle_min >= THRESHOLDS['DEEP_AWAY_MINUTES']:
            return 'DEEP_AWAY'
        if idle_min >= settings.get('rest_threshold', THRESHOLDS['SHORT_REST_MINUTES']):
            return 'SHORT_REST'

        # ── Top-3 classification model ─────────────────────────────────
        has_work = snap.has_work_window
        has_ent  = snap.has_entertainment_window

        if has_work and has_ent:
            return 'MIXED'

        if not has_work and not has_ent and snap.idle_seconds < 10:
            return 'UNRECOGNIZED_ACTIVE'

        work_cont_min = snap.work_continuous_seconds / 60.0
        focus_threshold = settings.get('focus_threshold', THRESHOLDS['FOCUS_MINUTES'])

        # --- Work states ---
        if has_work:
            if snap.is_ide:
                if snap.has_error_in_title:
                    return 'CODE_DEBUG'
                if work_cont_min >= focus_threshold:
                    return 'DEEP_FOCUS'
                return 'NORMAL_WORK'
            if snap.is_writing:
                return 'WRITING'
            if cat == 'COMMUNICATION':
                return 'MEETING'
            if work_cont_min >= focus_threshold:
                return 'DEEP_FOCUS'
            return 'NORMAL_WORK'

        if cat == 'COMMUNICATION':
            return 'MEETING'

        # --- Game state ---
        if cat == 'GAME' or 'GAME' in snap.top_categories:
            return 'GAMING'

        # --- Video states ---
        if cat in ('VIDEO', 'BROWSER_VIDEO'):
            if self._video_subtype is not None:
                _map = {
                    'DOCUMENTARY':   'VIDEO_DOCUMENTARY',
                    'ENTERTAINMENT': 'VIDEO_ENTERTAINMENT',
                    'HORROR':        'VIDEO_HORROR',
                    'GAMING':        'GAMING',
                }
                return _map.get(self._video_subtype, 'VIDEO_UNKNOWN')
            if self._video_start is None:
                self._video_start = now
                self._video_q_shown = False
            elapsed = now - self._video_start
            if (elapsed >= THRESHOLDS['VIDEO_CONFIRM_SECONDS']
                    and not self._video_q_shown
                    and settings.get('video_question_enabled', True)):
                self._pending_video_q = True
            return 'VIDEO_UNKNOWN'

        # Leaving video context → reset video tracking
        self._video_subtype = None
        self._video_start = None
        self._pending_video_q = False
        self._video_q_shown = False

        if cat == 'MUSIC':
            return 'MUSIC_WORK'

        # --- SOCIAL / DOPAMINE_CRASH ---
        if cat == 'SOCIAL':
            social_cont_min = snap.continuous_cat_seconds / 60.0
            if social_cont_min >= 60.0 and not self._crash_triggered:
                self._crash_triggered = True
                self._dopamine_entered = True
            if self._crash_triggered:
                return 'DOPAMINE_CRASH'
            return 'SOCIAL_MEDIA'

        if self._crash_triggered:
            self._crash_triggered = False

        return 'IDLE'

    # ------------------------------------------------------------------
    # Active pomodoro phase management
    # ------------------------------------------------------------------

    def _update_pom_phase(self, state_id: str) -> None:
        """Advance the active pomodoro state machine based on the current state."""
        now = time.monotonic()
        cfg = self._settings.get('pomodoro', {})
        work_secs = cfg.get('work_minutes', 25) * 60.0
        break_secs = cfg.get('break_minutes', 5) * 60.0

        is_work     = state_id in _WORK_STATES
        is_distract = state_id in _DISTRACT_STATES

        if self._pom_phase == '':
            # Start tracking when user enters any work state
            if is_work:
                self._pom_phase = 'WORK'
                self._pom_active_work_start = now

        elif self._pom_phase == 'WORK':
            if is_distract:
                # Distracting activity → reset
                self._pom_phase = ''
                self._pom_active_work_start = None
            elif is_work and self._pom_active_work_start is not None:
                if (now - self._pom_active_work_start) >= work_secs:
                    self._pom_phase = 'WORK_DONE'
            # Break states (idle) → pause in place (don't reset, don't advance)

        elif self._pom_phase == 'WORK_DONE':
            # Waiting for user to click "start break"
            if is_distract:
                # They started doing something distracting instead of resting → reset
                self._pom_phase = ''
                self._pom_active_work_start = None

        elif self._pom_phase == 'REST':
            # Countdown: UI shows remaining time; auto-advance when done
            if self._pom_active_rest_start is not None:
                if (now - self._pom_active_rest_start) >= break_secs:
                    self._pom_phase = 'REST_DONE'

        elif self._pom_phase == 'REST_DONE':
            # Waiting for user to click "start work"
            # Auto-confirm if user already resumed work without clicking
            if is_work:
                self._pom_streak += 1
                ds = self._settings.get('daily_stats')
                if isinstance(ds, dict):
                    ds['pomodoro_count'] = ds.get('pomodoro_count', 0) + 1
                self._pending_bubble = '🍅 番茄钟完成！专注力+1'
                self._pom_phase = 'WORK'
                self._pom_active_work_start = now
            elif is_distract:
                self._pom_phase = ''
                self._pom_active_work_start = None

    # ------------------------------------------------------------------
    # One-time bubble messages
    # ------------------------------------------------------------------

    def _check_one_time_bubbles(self, state_id: str) -> None:
        s = BRAIN_STATES.get(state_id, {})
        msg = s.get('bubble_message')
        if msg and state_id not in self._session_bubbles_shown:
            self._session_bubbles_shown.add(state_id)
            self._pending_bubble = msg

        overlay = current_time_overlay()
        late_msg = overlay.get('late_bubble')
        overlay_id = overlay['id']
        if late_msg and overlay_id not in self._session_bubbles_shown:
            if self._settings.get('late_night_reminder_enabled', True):
                self._session_bubbles_shown.add(overlay_id)
                self._pending_bubble = late_msg
