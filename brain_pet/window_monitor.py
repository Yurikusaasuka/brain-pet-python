"""Background thread that polls the active window and input state every ~1 second.

Detection strategy (two-tier):
  - Fast poll (1 s): foreground window via GetForegroundWindow — low overhead, low latency.
  - Slow scan (every 3rd poll ≈ 3 s): full EnumWindows Z-order scan for top-3 context.
  - WinEvent hook attempt: if available, fires on foreground change for near-instant response.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import queue
import re
import threading
import time
from collections import deque
from typing import Optional

try:
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    win32gui = None  # type: ignore
    win32process = None  # type: ignore
    WIN32_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_AVAILABLE = False

try:
    class _LASTINPUTINFO(ctypes.Structure):
        _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_ulong)]
    CTYPES_AVAILABLE = True
except Exception:
    CTYPES_AVAILABLE = False

from .constants import (
    APP_CATEGORIES, IDE_PROCESSES, WRITING_APPS,
    AI_PROCESSES, AI_TITLE_KEYWORDS,
    GAME_PROCESSES, GAME_TITLE_KEYWORDS, GAME_WINDOW_CLASSES,
    WORK_TITLE_KEYWORDS,
    ENTERTAINMENT_CATEGORIES,
)

# Window title keywords that signal an active debugging/error session
_ERROR_KEYWORDS = frozenset({
    'error', 'exception', 'traceback', 'fail', 'failed', 'panic',
    'crash', 'fatal', 'abort', 'syntax', 'undefined', 'cannot',
    'warning', 'stderr', 'stack trace',
    '报错', '错误', '异常', '出错', '调试',
})

# System process names to skip when enumerating top windows
_SYSTEM_PROCESSES = frozenset({
    'explorer', 'taskbar', 'searchhost', 'startmenuexperiencehost',
    'shellexperiencehost', 'applicationframehost', 'systemsettings',
    'textinputhost', 'lockapp', 'dwm', 'winlogon', 'csrss',
    'brain', 'brain-pet', 'python', 'pythonw',
})


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def get_idle_seconds() -> float:
    if not CTYPES_AVAILABLE:
        return 0.0
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0
    except Exception:
        return 0.0


def is_fullscreen_app_active() -> bool:
    """Return True if the foreground window covers the full primary screen."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        return (rect.right - rect.left >= screen_w and
                rect.bottom - rect.top >= screen_h)
    except Exception:
        return False


def _count_visible_windows() -> int:
    if not WIN32_AVAILABLE:
        return 0
    count = [0]

    def _cb(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd).strip():
                count[0] += 1
        except Exception:
            pass

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass
    return count[0]


def _get_foreground_hwnd() -> int:
    """Return HWND of the foreground window (0 on failure)."""
    try:
        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        return 0


def _hwnd_to_proc_title(hwnd: int) -> tuple[str, str]:
    """Return (process_name_lower, window_title_lower) for a given HWND."""
    if not (WIN32_AVAILABLE and PSUTIL_AVAILABLE) or not hwnd:
        return '', ''
    try:
        title = win32gui.GetWindowText(hwnd).lower()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_name = psutil.Process(pid).name().lower()
        return process_name, title
    except Exception:
        return '', ''


def _get_active_info() -> tuple[str, str]:
    """Return (process_name_lower, window_title_lower) for the foreground window."""
    hwnd = _get_foreground_hwnd()
    return _hwnd_to_proc_title(hwnd)


def _get_window_class(hwnd: int) -> str:
    """Return the window class name for an HWND (empty string on failure)."""
    if not WIN32_AVAILABLE or not hwnd:
        return ''
    try:
        return win32gui.GetClassName(hwnd).lower()
    except Exception:
        return ''


def get_top_windows(n: int = 3, fg_hwnd: int = 0) -> list[tuple[str, str]]:
    """Return (process_name, window_title) for the top N visible user windows (Z-order).

    The foreground window (fg_hwnd) is always inserted at position 0 so that the
    current active window is never missed, even if EnumWindows returns it late due
    to timing.
    """
    if not (WIN32_AVAILABLE and PSUTIL_AVAILABLE):
        return []

    # Seed with the known foreground window so it's always represented
    fg_entry: Optional[tuple[str, str]] = None
    if fg_hwnd:
        fg_proc, fg_title = _hwnd_to_proc_title(fg_hwnd)
        if fg_proc and not any(s in fg_proc for s in _SYSTEM_PROCESSES):
            fg_entry = (fg_proc.replace('.exe', ''), fg_title)

    windows: list[tuple[str, str]] = []
    seen_titles: set[str] = set()

    if fg_entry:
        windows.append(fg_entry)
        seen_titles.add(fg_entry[1][:60])

    def _cb(hwnd, _):
        if len(windows) >= n * 6:   # gather more candidates, trim later
            return
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if not title or not title.strip():
                return
            tkey = title.lower()[:60]
            if tkey in seen_titles:
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid).name().lower().replace('.exe', '')
            if any(s in proc for s in _SYSTEM_PROCESSES):
                return
            seen_titles.add(tkey)
            windows.append((proc, title.lower()))
        except Exception:
            pass

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass

    return windows[:n]


# ---------------------------------------------------------------------------
# Categorisation helpers
# ---------------------------------------------------------------------------

def _title_has_keyword(title: str, keyword: str) -> bool:
    """Match keyword as a whole word, not as substring of a path component."""
    pattern = r'(?<![/\\a-zA-Z0-9])' + re.escape(keyword) + r'(?![/\\a-zA-Z0-9])'
    return bool(re.search(pattern, title, re.IGNORECASE))


def categorize(process_name: str, window_title: str,
               hwnd: int = 0) -> Optional[str]:
    # WORK first — prevents path fragments like 'game/' from shadowing IDE detection
    for kw in APP_CATEGORIES.get('WORK', []):
        if kw in process_name:
            return 'WORK'
    # AI title keywords (browser-based AI tools)
    for kw in AI_TITLE_KEYWORDS:
        if _title_has_keyword(window_title, kw):
            return 'WORK'
    # General work-related web tool title keywords (GitHub, Jira, etc.)
    for kw in WORK_TITLE_KEYWORDS:
        if kw in window_title:
            return 'WORK'

    # COMMUNICATION
    for kw in APP_CATEGORIES.get('COMMUNICATION', []):
        if kw in process_name:
            return 'COMMUNICATION'

    # VIDEO (native player by process name)
    for kw in APP_CATEGORIES.get('VIDEO', []):
        if kw in process_name:
            return 'VIDEO'

    # BROWSER_VIDEO — title-based, use word-boundary guard
    for kw in APP_CATEGORIES.get('BROWSER_VIDEO', []):
        if _title_has_keyword(window_title, kw):
            return 'BROWSER_VIDEO'

    # MUSIC
    for kw in APP_CATEGORIES.get('MUSIC', []):
        if kw in process_name:
            return 'MUSIC'

    # SOCIAL — title-based, use word-boundary guard
    for kw in APP_CATEGORIES.get('SOCIAL', []):
        if _title_has_keyword(window_title, kw):
            return 'SOCIAL'

    # GAME — process name, title keywords, and window class name
    for kw in GAME_PROCESSES:
        if kw in process_name:
            return 'GAME'
    for kw in GAME_TITLE_KEYWORDS:
        if _title_has_keyword(window_title, kw):
            return 'GAME'
    if hwnd:
        wclass = _get_window_class(hwnd)
        for kw in GAME_WINDOW_CLASSES:
            if kw in wclass:
                return 'GAME'

    return None


def is_ide(process_name: str) -> bool:
    return any(kw in process_name for kw in IDE_PROCESSES)


def is_writing(process_name: str, title: str) -> bool:
    return any(kw in process_name or kw in title for kw in WRITING_APPS)


def is_ai_app(process_name: str, title: str) -> bool:
    """Return True if the active app is an AI assistant (browser-based or native)."""
    for kw in AI_PROCESSES:
        if kw in process_name:
            return True
    for kw in AI_TITLE_KEYWORDS:
        if kw in title:
            return True
    return False


# ---------------------------------------------------------------------------
# Snapshot object passed to the state machine
# ---------------------------------------------------------------------------

class MonitorSnapshot:
    __slots__ = (
        'process_name', 'window_title', 'category',
        'idle_seconds', 'window_count',
        'recent_switches',
        'continuous_cat_seconds',
        'work_continuous_seconds',   # seconds since work app continuously in top-3
        'is_ide', 'is_writing', 'is_ai',
        'has_error_in_title',
        # Top-3 window awareness
        'top_windows',        # list[(proc, title)] up to 3
        'top_categories',     # list[Optional[str]] categories of top windows
        'has_work_window',    # True if any top-3 window is WORK
        'has_entertainment_window',  # True if any top-3 window is entertainment
        'is_fullscreen',
    )

    def __init__(self) -> None:
        self.process_name: str = ''
        self.window_title: str = ''
        self.category: Optional[str] = None
        self.idle_seconds: float = 0.0
        self.window_count: int = 0
        self.recent_switches: list[float] = []
        self.continuous_cat_seconds: float = 0.0
        self.work_continuous_seconds: float = 0.0
        self.is_ide: bool = False
        self.is_writing: bool = False
        self.is_ai: bool = False
        self.has_error_in_title: bool = False
        self.top_windows: list[tuple[str, str]] = []
        self.top_categories: list[Optional[str]] = []
        self.has_work_window: bool = False
        self.has_entertainment_window: bool = False
        self.is_fullscreen: bool = False


# ---------------------------------------------------------------------------
# Background monitor
# ---------------------------------------------------------------------------

class WindowMonitor:
    """Daemon thread polling system state and pushing MonitorSnapshot.

    Two-tier polling:
      - Every poll (POLL_INTERVAL ≈ 1 s): cheap foreground-window read.
      - Every SLOW_SCAN_EVERY polls: expensive EnumWindows Z-order scan.
    This keeps foreground-change latency ≤ 1 s while keeping CPU load low.
    """

    POLL_INTERVAL   = 1.0   # seconds between polls (was 2.0)
    SLOW_SCAN_EVERY = 3     # run full EnumWindows scan every N polls

    def __init__(self, out_queue: 'queue.Queue[MonitorSnapshot]') -> None:
        self._q = out_queue
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name='brain-pet-monitor'
        )
        self._last_process: str = ''
        self._switch_times: deque[float] = deque()
        self._cat_start: float = time.monotonic()
        self._last_cat: Optional[str] = None
        # Track work-window continuity separately from foreground category
        self._work_cat_start: float = time.monotonic()
        self._last_had_work: bool = False
        # Top-window cache (refreshed on slow scan)
        self._cached_top_wins: list[tuple[str, str]] = []
        self._cached_window_count: int = 0
        self._poll_count: int = 0

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._poll()
            except Exception:
                pass
            self._stop.wait(self.POLL_INTERVAL)

    def _poll(self) -> None:
        self._poll_count += 1
        now = time.monotonic()

        # Fast path: get current foreground window HWND immediately
        fg_hwnd = _get_foreground_hwnd()
        process_name, title = _hwnd_to_proc_title(fg_hwnd)

        # Track app switches (process change)
        if process_name and process_name != self._last_process:
            self._switch_times.append(now)
            self._last_process = process_name

        # Prune switches older than 3 minutes
        cutoff = now - 180.0
        while self._switch_times and self._switch_times[0] < cutoff:
            self._switch_times.popleft()

        # Foreground category (pass hwnd for window-class game detection)
        cat = categorize(process_name, title, fg_hwnd)
        if cat != self._last_cat:
            self._last_cat = cat
            self._cat_start = now

        # Slow scan: refresh top-3 Z-order list and window count periodically
        do_slow_scan = (self._poll_count % self.SLOW_SCAN_EVERY == 0
                        or not self._cached_top_wins)
        if do_slow_scan:
            self._cached_top_wins = get_top_windows(3, fg_hwnd)
            self._cached_window_count = _count_visible_windows()

        top_wins = self._cached_top_wins
        # Fallback: if enumeration returned nothing, use foreground window
        if not top_wins and process_name:
            top_wins = [(process_name.replace('.exe', ''), title)]

        top_cats = [categorize(p, t) for p, t in top_wins]
        has_work = 'WORK' in top_cats or cat == 'WORK'
        has_ent = any(c in ENTERTAINMENT_CATEGORIES for c in top_cats if c)
        if not has_ent and cat in ENTERTAINMENT_CATEGORIES:
            has_ent = True

        # Work-window continuity: resets only when work vanishes from top 3
        if has_work and not self._last_had_work:
            self._work_cat_start = now
        elif not has_work:
            self._work_cat_start = now
        self._last_had_work = has_work

        snap = MonitorSnapshot()
        snap.process_name = process_name
        snap.window_title = title
        snap.category = cat
        snap.idle_seconds = get_idle_seconds()
        snap.window_count = self._cached_window_count
        snap.recent_switches = list(self._switch_times)
        snap.continuous_cat_seconds = now - self._cat_start
        snap.work_continuous_seconds = (now - self._work_cat_start) if has_work else 0.0
        snap.is_ide = is_ide(process_name)
        snap.is_ai = is_ai_app(process_name, title)
        snap.is_writing = is_writing(process_name, title) or snap.is_ai
        snap.has_error_in_title = any(kw in title for kw in _ERROR_KEYWORDS)
        snap.top_windows = top_wins
        snap.top_categories = top_cats
        snap.has_work_window = has_work
        snap.has_entertainment_window = has_ent
        snap.is_fullscreen = is_fullscreen_app_active()

        try:
            self._q.put_nowait(snap)
        except queue.Full:
            try:
                self._q.get_nowait()
                self._q.put_nowait(snap)
            except queue.Empty:
                pass
