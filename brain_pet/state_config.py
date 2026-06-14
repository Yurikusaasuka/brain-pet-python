"""Brain state definitions.

Each state dict:
  id            str
  name          str  (Chinese-friendly short label)
  regions       {region_id: {'intensity': 0-1, 'color': '#RRGGBB', 'effect': str|None}}
                Omitted regions default to intensity 0.
  animation     'pulse'|'breathe'|'flash'|'wave'|'static'|'irregular'|'sparkle'|'jitter'
  pulse_speed   animation cycle in ms
  bubble_message  str or None  (shown once per session)
  primary_color   str  – used for tray icon and status bar

Characteristic hue per region:
  pfc (frontal)  → blue        #3498DB
  parietal       → teal        #17A589
  temporal       → amber-gold  #D68910
  occipital      → saffron     #CA6F1E
  cerebellum     → green       #27AE60
  limbic         → crimson     #C0392B  (synthetically drawn — no PNG)
  broca          → mint        #1ABC9C  (synthetically drawn — no PNG)
  brainstem      → dark red    #922B21
"""
from __future__ import annotations

from .constants import ALL_REGION_IDS

# ---------------------------------------------------------------------------
# Reusable region dicts
# ---------------------------------------------------------------------------

def _all_regions(intensity: float, color: str) -> dict:
    return {rid: {'intensity': intensity, 'color': color} for rid in ALL_REGION_IDS}

_OVERLOAD_REGIONS = _all_regions(1.0, '#E74C3C')   # all red – alarm state
_FLOW_REGIONS     = _all_regions(1.0, '#FFD700')   # all gold – flow state

# Sleep: dreaming activity — each region at natural color, very low intensity
_SLEEP_REGIONS: dict[str, dict] = {
    'limbic':     {'intensity': 0.12, 'color': '#1B2631'},   # deep blue
    'temporal':   {'intensity': 0.08, 'color': '#D68910'},   # faint amber – memory consolidation
    'occipital':  {'intensity': 0.06, 'color': '#8E44AD'},   # faint purple – visual dreams
    'pfc_left':   {'intensity': 0.04, 'color': '#3498DB'},
    'pfc_right':  {'intensity': 0.04, 'color': '#3498DB'},
    'brainstem':  {'intensity': 0.10, 'color': '#922B21'},   # maintains basic life functions
}

# Rest state: all regions dim, each in their natural characteristic hue
_REST_REGIONS = {
    'pfc_left':   {'intensity': 0.12, 'color': '#3498DB'},
    'pfc_right':  {'intensity': 0.12, 'color': '#3498DB'},
    'parietal':   {'intensity': 0.10, 'color': '#17A589'},
    'temporal':   {'intensity': 0.12, 'color': '#D68910', 'effect': 'temporal_lower'},
    'occipital':  {'intensity': 0.10, 'color': '#CA6F1E'},
    'limbic':     {'intensity': 0.20, 'color': '#C0392B'},
    'cerebellum': {'intensity': 0.10, 'color': '#27AE60'},
    'broca':      {'intensity': 0.08, 'color': '#1ABC9C'},
    'brainstem':  {'intensity': 0.08, 'color': '#922B21'},
}

# ---------------------------------------------------------------------------
# State definitions
# ---------------------------------------------------------------------------

BRAIN_STATES: dict[str, dict] = {

    # =========================================================================
    # WORK STATES
    # =========================================================================
    'DEEP_FOCUS': {
        'id': 'DEEP_FOCUS',
        'name': '深度专注',
        'regions': {
            'pfc_left':  {'intensity': 1.0, 'color': '#3498DB', 'effect': 'frontal_focus'},
            'pfc_right': {'intensity': 1.0, 'color': '#3498DB', 'effect': 'frontal_focus'},
            'parietal':  {'intensity': 0.4, 'color': '#17A589'},
        },
        'animation': 'breathe',   # breathe (0.3-1.0): lobes never go fully dark
        'pulse_speed': 3000,
        'bubble_message': None,
        'primary_color': '#3498DB',
    },
    'NORMAL_WORK': {
        'id': 'NORMAL_WORK',
        'name': '工作中',
        'regions': {
            'pfc_left':  {'intensity': 0.7, 'color': '#3498DB'},
            'pfc_right': {'intensity': 0.7, 'color': '#3498DB'},
            'broca':     {'intensity': 0.5, 'color': '#1ABC9C'},
        },
        'animation': 'static',
        'pulse_speed': 2000,
        'bubble_message': None,
        'primary_color': '#3498DB',
    },
    'CODE_DEBUG': {
        'id': 'CODE_DEBUG',
        'name': '调试代码',
        'regions': {
            'pfc_left':  {'intensity': 0.9, 'color': '#2980B9'},
            'pfc_right': {'intensity': 0.9, 'color': '#2980B9'},
            'parietal':  {'intensity': 0.8, 'color': '#E67E22'},
        },
        'animation': 'flash',
        'pulse_speed': 500,
        'bubble_message': None,
        'primary_color': '#E67E22',
    },
    'WRITING': {
        'id': 'WRITING',
        'name': '写作中',
        'regions': {
            'broca':     {'intensity': 1.0, 'color': '#1ABC9C'},
            'pfc_left':  {'intensity': 0.6, 'color': '#3498DB'},
            'pfc_right': {'intensity': 0.6, 'color': '#3498DB'},
        },
        'animation': 'wave',
        'pulse_speed': 3000,
        'bubble_message': None,
        'primary_color': '#1ABC9C',
    },
    'MEETING': {
        'id': 'MEETING',
        'name': '开会中',
        'regions': {
            'temporal':  {'intensity': 1.0, 'color': '#D68910'},
            'broca':     {'intensity': 0.8, 'color': '#1ABC9C'},
        },
        'animation': 'pulse',
        'pulse_speed': 1500,
        'bubble_message': None,
        'primary_color': '#D68910',
    },
    'OVERLOAD': {
        'id': 'OVERLOAD',
        'name': '过载',
        'regions': _OVERLOAD_REGIONS,
        'animation': 'irregular',
        'pulse_speed': 200,
        'bubble_message': '事情有点多… \U0001f635',
        'primary_color': '#E74C3C',
    },

    # =========================================================================
    # ENTERTAINMENT STATES
    # =========================================================================
    'VIDEO_UNKNOWN': {
        'id': 'VIDEO_UNKNOWN',
        'name': '看视频',
        'regions': {
            'occipital': {'intensity': 0.8, 'color': '#CA6F1E'},
        },
        'animation': 'pulse',
        'pulse_speed': 1500,
        'bubble_message': None,
        'primary_color': '#CA6F1E',
    },
    'VIDEO_DOCUMENTARY': {
        'id': 'VIDEO_DOCUMENTARY',
        'name': '纪录片',
        'regions': {
            'occipital': {'intensity': 0.9, 'color': '#F1C40F'},
            'temporal':  {'intensity': 0.7, 'color': '#D68910'},
            'pfc_left':  {'intensity': 0.5, 'color': '#3498DB'},
            'pfc_right': {'intensity': 0.5, 'color': '#3498DB'},
        },
        'animation': 'pulse',
        'pulse_speed': 2500,
        'bubble_message': None,
        'primary_color': '#F1C40F',
    },
    'VIDEO_ENTERTAINMENT': {
        'id': 'VIDEO_ENTERTAINMENT',
        'name': '娱乐视频',
        'regions': {
            'occipital': {'intensity': 0.8, 'color': '#E8865A'},
            'limbic':    {'intensity': 0.9, 'color': '#C0392B'},
        },
        'animation': 'wave',
        'pulse_speed': 800,
        'bubble_message': None,
        'primary_color': '#E8865A',
    },
    'VIDEO_HORROR': {
        'id': 'VIDEO_HORROR',
        'name': '恐怖视频',
        'regions': {
            'occipital': {'intensity': 1.0, 'color': '#8E44AD'},
            'limbic':    {'intensity': 1.0, 'color': '#6C3483'},
        },
        'animation': 'flash',
        'pulse_speed': 300,
        'bubble_message': None,
        'primary_color': '#8E44AD',
    },
    'MUSIC_WORK': {
        'id': 'MUSIC_WORK',
        'name': '边听音乐边工作',
        'regions': {
            'temporal':  {'intensity': 0.45, 'color': '#D68910', 'effect': 'temporal_upper'},
            'pfc_left':  {'intensity': 0.8,  'color': '#3498DB'},
            'pfc_right': {'intensity': 0.8,  'color': '#3498DB'},
        },
        'animation': 'wave',
        'pulse_speed': 2000,
        'bubble_message': None,
        'primary_color': '#D68910',
    },
    'SOCIAL_MEDIA': {
        'id': 'SOCIAL_MEDIA',
        'name': '刷社交媒体',
        'regions': {
            'limbic':    {'intensity': 0.6, 'color': '#C0392B'},
            'pfc_left':  {'intensity': 0.2, 'color': '#85B0D0'},
            'pfc_right': {'intensity': 0.2, 'color': '#85B0D0'},
        },
        'animation': 'breathe',
        'pulse_speed': 4000,
        'bubble_message': None,
        'primary_color': '#C0392B',
    },
    'GAMING': {
        'id': 'GAMING',
        'name': '游戏中',
        'regions': {
            'cerebellum': {'intensity': 0.9, 'color': '#27AE60'},
            'occipital':  {'intensity': 0.8, 'color': '#CA6F1E'},
            'parietal':   {'intensity': 0.7, 'color': '#17A589'},
            'pfc_left':   {'intensity': 0.5, 'color': '#3498DB'},
            'pfc_right':  {'intensity': 0.5, 'color': '#3498DB'},
        },
        'animation': 'pulse',
        'pulse_speed': 800,
        'bubble_message': None,
        'primary_color': '#27AE60',
    },

    # =========================================================================
    # REST STATES
    # =========================================================================
    'SHORT_REST': {
        'id': 'SHORT_REST',
        'name': '小憩',
        'regions': _REST_REGIONS,
        'animation': 'breathe',
        'pulse_speed': 4000,
        'bubble_message': None,
        'primary_color': '#85C1E9',
    },
    'DEEP_AWAY': {
        'id': 'DEEP_AWAY',
        'name': '长时间离开',
        'regions': {
            'cerebellum': {'intensity': 0.05, 'color': '#27AE60'},
            'brainstem':  {'intensity': 0.08, 'color': '#922B21'},
        },
        'animation': 'pulse',
        'pulse_speed': 10000,
        'bubble_message': None,
        'primary_color': '#27AE60',
    },

    # =========================================================================
    # MANUAL STATES (right-click menu)
    # =========================================================================
    'EXERCISE': {
        'id': 'EXERCISE',
        'name': '运动中',
        'regions': {
            'cerebellum': {'intensity': 1.0, 'color': '#00D66B'},
            'parietal':   {'intensity': 0.8, 'color': '#27AE60'},
            'brainstem':  {'intensity': 0.3, 'color': '#922B21'},
        },
        'animation': 'pulse',
        'pulse_speed': 600,
        'bubble_message': None,
        'primary_color': '#00D66B',
    },
    'EATING': {
        'id': 'EATING',
        'name': '用餐中',
        'regions': {
            'limbic':   {'intensity': 0.9, 'color': '#E07B00'},
            'temporal': {'intensity': 0.6, 'color': '#D68910'},
        },
        'animation': 'wave',
        'pulse_speed': 1200,
        'bubble_message': None,
        'primary_color': '#E07B00',
    },
    'SLEEPING': {
        'id': 'SLEEPING',
        'name': '睡眠',
        'regions': _SLEEP_REGIONS,
        'animation': 'breathe',
        'pulse_speed': 8000,
        'bubble_message': None,
        'primary_color': '#1B2631',
    },
    'WALKING': {
        'id': 'WALKING',
        'name': '散步中',
        'regions': {
            # DMN (Default Mode Network) wandering — all regions lit softly
            'pfc_left':   {'intensity': 0.25, 'color': '#D6EAF8', 'effect': 'wander'},
            'pfc_right':  {'intensity': 0.25, 'color': '#D6EAF8', 'effect': 'wander'},
            'parietal':   {'intensity': 0.20, 'color': '#D6EAF8', 'effect': 'wander'},
            'temporal':   {'intensity': 0.20, 'color': '#D6EAF8', 'effect': 'wander'},
            'occipital':  {'intensity': 0.15, 'color': '#D6EAF8', 'effect': 'wander'},
            'cerebellum': {'intensity': 0.18, 'color': '#D6EAF8', 'effect': 'wander'},
            'limbic':     {'intensity': 0.35, 'color': '#AED6F1'},
        },
        'animation': 'breathe',
        'pulse_speed': 6000,
        'bubble_message': None,
        'primary_color': '#AED6F1',
    },
    'CREATIVE': {
        'id': 'CREATIVE',
        'name': '创意模式',
        'regions': {
            'pfc_right': {'intensity': 1.0, 'color': '#FF6B6B', 'effect': 'frontal_creative'},
            'pfc_left':  {'intensity': 0.6, 'color': '#E74C3C'},
            'parietal':  {'intensity': 0.9, 'color': '#E74C3C'},
        },
        'animation': 'sparkle',
        'pulse_speed': 400,
        'bubble_message': None,
        'primary_color': '#FF6B6B',
    },

    # =========================================================================
    # SPECIAL STATES
    # =========================================================================
    'FLOW_STATE': {
        'id': 'FLOW_STATE',
        'name': '心流',
        'regions': _FLOW_REGIONS,
        'animation': 'sparkle',
        'pulse_speed': 400,
        'bubble_message': '心流状态！\U0001f525',
        'primary_color': '#FFD700',
    },
    'FOCUS_STREAK': {
        'id': 'FOCUS_STREAK',
        'name': '专注连胜',
        'regions': {
            'pfc_left':  {'intensity': 1.0, 'color': '#FFD700'},
            'pfc_right': {'intensity': 1.0, 'color': '#FFD700'},
            'parietal':  {'intensity': 0.6, 'color': '#F39C12'},
        },
        'animation': 'sparkle',
        'pulse_speed': 400,
        'bubble_message': None,
        'primary_color': '#FFD700',
    },
    'PROCRASTINATION': {
        'id': 'PROCRASTINATION',
        'name': '拖延中',
        'regions': {
            'pfc_left':  {'intensity': 0.7, 'color': '#3498DB'},
            'pfc_right': {'intensity': 0.7, 'color': '#3498DB'},
            'limbic':    {'intensity': 0.7, 'color': '#C0392B'},
        },
        'animation': 'jitter',
        'pulse_speed': 300,
        'bubble_message': None,
        'primary_color': '#9B59B6',
    },
    'STRESS_HIGH': {
        'id': 'STRESS_HIGH',
        'name': '压力过高',
        'regions': {
            'limbic':    {'intensity': 1.0, 'color': '#E74C3C'},
            'pfc_left':  {'intensity': 0.6, 'color': '#E74C3C'},
            'pfc_right': {'intensity': 0.6, 'color': '#E74C3C'},
            'brainstem': {'intensity': 0.4, 'color': '#922B21'},
        },
        'animation': 'flash',
        'pulse_speed': 300,
        'bubble_message': '休息一下？\U0001f499',
        'primary_color': '#E74C3C',
    },
    'DOPAMINE_CRASH': {
        'id': 'DOPAMINE_CRASH',
        'name': '多巴胺耗尽',
        'regions': {
            'limbic':    {'intensity': 0.08, 'color': '#C0392B'},
            'pfc_left':  {'intensity': 0.05, 'color': '#85B0D0'},
            'pfc_right': {'intensity': 0.05, 'color': '#85B0D0'},
        },
        'animation': 'breathe',
        'pulse_speed': 6000,
        'bubble_message': '多巴胺有点耗尽了… 出去走走？',
        'primary_color': '#C0392B',
    },

    # =========================================================================
    # NEW STATES (top-3 window awareness)
    # =========================================================================
    'MIXED': {
        'id': 'MIXED',
        'name': '混合模式',
        'regions': {
            'pfc_left':  {'intensity': 0.7, 'color': '#3498DB'},
            'pfc_right': {'intensity': 0.7, 'color': '#3498DB'},
            'occipital': {'intensity': 0.5, 'color': '#CA6F1E'},
            'limbic':    {'intensity': 0.4, 'color': '#C0392B'},
        },
        'animation': 'wave',
        'pulse_speed': 2500,
        'bubble_message': None,
        'primary_color': '#9B59B6',
    },
    'UNRECOGNIZED_ACTIVE': {
        'id': 'UNRECOGNIZED_ACTIVE',
        'name': '未知活动',
        'regions': {
            'pfc_left':  {'intensity': 0.25, 'color': '#85C1E9'},
            'pfc_right': {'intensity': 0.25, 'color': '#85C1E9'},
        },
        'animation': 'breathe',
        'pulse_speed': 3000,
        'bubble_message': None,
        'primary_color': '#85C1E9',
    },

    # =========================================================================
    # DEFAULT / IDLE
    # =========================================================================
    'IDLE': {
        'id': 'IDLE',
        'name': '空闲',
        'regions': {
            'pfc_left':  {'intensity': 0.15, 'color': '#3498DB'},
            'pfc_right': {'intensity': 0.15, 'color': '#3498DB'},
            'limbic':    {'intensity': 0.20, 'color': '#C0392B'},
        },
        'animation': 'breathe',
        'pulse_speed': 4000,
        'bubble_message': None,
        'primary_color': '#85C1E9',
    },
}

# ---------------------------------------------------------------------------
# Time overlays – brightness multiplier applied on top of any state
# ---------------------------------------------------------------------------
TIME_OVERLAYS: dict[str, dict] = {
    'MORNING': {
        'id': 'MORNING',
        'name': '清晨',
        'brightness': 0.78,
        'late_bubble': None,
    },
    'PEAK': {
        'id': 'PEAK',
        'name': '高峰时段',
        'brightness': 1.0,
        'late_bubble': None,
    },
    'AFTERNOON_DIP': {
        'id': 'AFTERNOON_DIP',
        'name': '午后低谷',
        'brightness': 0.88,
        'late_bubble': None,
        'drowsy': True,
    },
    'AFTERNOON': {
        'id': 'AFTERNOON',
        'name': '下午恢复',
        'brightness': 0.95,
        'late_bubble': None,
    },
    'EVENING': {
        'id': 'EVENING',
        'name': '傍晚',
        'brightness': 0.82,
        'late_bubble': None,
    },
    'NIGHT_EARLY': {
        'id': 'NIGHT_EARLY',
        'name': '晚间',
        'brightness': 0.85,
        'late_bubble': None,
    },
    'NIGHT': {
        'id': 'NIGHT',
        'name': '夜间',
        'brightness': 0.72,
        'late_bubble': '快深夜了… \U0001f319',
    },
    'LATE_NIGHT': {
        'id': 'LATE_NIGHT',
        'name': '深夜',
        'brightness': 0.62,
        'late_bubble': '还没睡？\U0001f634',
    },
}

# ---------------------------------------------------------------------------
# Per-state visual boost  (brightness_mult, saturation_mult)
# Applied after region compositing to make each state visually distinct.
# saturation < 1.0 = slightly muted  |  > 1.0 = vivid/intense
# brightness > 1.0 = glowing bright  |  < 1.0 = dim/subdued
# RULE: never reduce saturation below 0.40 — use low intensity instead of gray
# ---------------------------------------------------------------------------
STATE_VISUAL_BOOST: dict[str, tuple[float, float]] = {
    'DEEP_FOCUS':          (1.10, 1.30),
    'NORMAL_WORK':         (1.00, 1.10),
    'CODE_DEBUG':          (1.05, 1.35),
    'WRITING':             (1.00, 1.15),
    'MEETING':             (1.00, 1.15),
    'OVERLOAD':            (1.20, 1.20),
    'VIDEO_UNKNOWN':       (1.00, 1.10),
    'VIDEO_DOCUMENTARY':   (1.00, 1.20),
    'VIDEO_ENTERTAINMENT': (1.05, 1.25),
    'VIDEO_HORROR':        (1.00, 1.10),
    'MUSIC_WORK':          (1.00, 1.15),
    'SOCIAL_MEDIA':        (0.85, 0.70),
    'GAMING':              (1.05, 1.20),
    'SHORT_REST':          (0.78, 0.60),
    'DEEP_AWAY':           (0.60, 0.50),
    'EXERCISE':            (1.10, 1.30),
    'EATING':              (1.00, 1.15),
    'SLEEPING':            (0.50, 0.45),   # dim but keep hue (no gray)
    'WALKING':             (0.90, 0.85),
    'CREATIVE':            (1.10, 1.40),
    'FLOW_STATE':          (1.30, 1.60),
    'FOCUS_STREAK':        (1.20, 1.50),
    'PROCRASTINATION':     (1.00, 1.10),
    'STRESS_HIGH':         (1.15, 1.20),
    'DOPAMINE_CRASH':      (0.65, 0.45),   # dim but keep hue
    'MIXED':               (1.00, 1.10),
    'UNRECOGNIZED_ACTIVE': (0.90, 0.90),
    'IDLE':                (0.90, 0.90),
}
