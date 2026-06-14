from __future__ import annotations

import math
import random


def get_animation_multiplier(style: str, pulse_speed_ms: int, elapsed_ms: float) -> float:
    t = (elapsed_ms % pulse_speed_ms) / pulse_speed_ms
    if style == 'pulse':
        return 0.5 + 0.5 * math.sin(2 * math.pi * t)
    elif style == 'breathe':
        return 0.3 + 0.7 * (math.sin(math.pi * t) ** 2)
    elif style == 'flash':
        # Sharp on/off: fully lit for 40% of cycle, fully dark for 60%.
        # The dark phase drops to 0.0 (not 0.1) for maximum visual contrast.
        return 1.0 if t < 0.4 else 0.0
    elif style == 'wave':
        return 0.4 + 0.6 * math.sin(2 * math.pi * t)
    elif style == 'static':
        return 1.0
    elif style == 'irregular':
        # Wide range including near-zero so the irregular shaking is clearly visible.
        return random.uniform(0.0, 1.0)
    elif style == 'sparkle':
        # Mostly bright with occasional full-off flicker for a star-burst feel.
        return random.choice([1.0, 1.0, 0.9, 0.0])
    elif style == 'jitter':
        return random.uniform(0.0, 1.0)
    return 1.0
