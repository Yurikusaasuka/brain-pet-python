"""
Spatial intensity masks for sub-region glow effects within brain region PNG layers.

Each function returns an 'L'-mode PIL Image (same size as the region layer).
  255 = full glow intensity at that pixel
  0   = no glow at that pixel
The mask is multiplied element-wise against the region's alpha channel before
the glow overlay is applied, so transparent areas are never painted.
"""
from __future__ import annotations

import math
from PIL import Image, ImageDraw, ImageFilter
from typing import Optional


def get_region_glow_mask(
    region_id: str,
    effect: Optional[str],
    w: int,
    h: int,
    elapsed_ms: float = 0.0,
) -> Image.Image:
    """Return the spatial glow mask for the given effect, or uniform 255 if none."""
    if not effect or effect == 'uniform':
        return Image.new('L', (w, h), 255)
    if effect == 'frontal_focus':
        return _frontal_focus(w, h)
    if effect == 'frontal_creative':
        return _frontal_creative(w, h, elapsed_ms)
    if effect == 'temporal_upper':
        return _bilinear_gradient(w, h, tl=255, tr=255, bl=80, br=80)
    if effect == 'temporal_lower':
        return _bilinear_gradient(w, h, tl=80, tr=80, bl=230, br=230)
    if effect == 'wander':
        # Region-specific phase so each brain area wanders at its own pace
        phase_offset = (hash(region_id) & 0xFF) / 256.0
        return _wander(w, h, elapsed_ms, phase_offset)
    return Image.new('L', (w, h), 255)


# ---------------------------------------------------------------------------
# Gradient helpers
# ---------------------------------------------------------------------------

def _bilinear_gradient(w: int, h: int, tl: int, tr: int, bl: int, br: int) -> Image.Image:
    """
    Create a smooth bilinear gradient from four corner values (0-255).
    Extremely fast: creates a 2×2 source and upscales with BILINEAR.
    """
    src = Image.frombytes('L', (2, 2), bytes([tl, tr, bl, br]))
    return src.resize((w, h), Image.BILINEAR)


def _frontal_focus(w: int, h: int) -> Image.Image:
    """
    Area-11 (orbitofrontal / anterior PFC) brighter → left-bottom quadrant.
    Areas 1-2 (primary motor / posterior frontal) dimmer → right side.
    Assumes standard lateral view: rostral (front) = image left, caudal = image right.
    Corner values: TL=220, TR=100, BL=255, BR=115
    """
    return _bilinear_gradient(w, h, tl=220, tr=100, bl=255, br=115)


def _wander(w: int, h: int, elapsed_ms: float, phase_offset: float = 0.0) -> Image.Image:
    """
    DMN (Default Mode Network) slow wandering glow for WALKING / relaxed states.
    Three soft spots drift independently across the full brain area.
    Much slower and more diffuse than frontal_creative.
    """
    mask = Image.new('L', (w, h), 110)   # moderate ambient base
    draw = ImageDraw.Draw(mask)
    spot_r = max(6, int(min(w, h) * 0.18))

    for speed, base_ph in [(0.22, 0.00), (0.35, 0.38), (0.17, 0.71)]:
        t = (elapsed_ms / 10000.0 * speed + base_ph + phase_offset) % 1.0
        cx = int(w * (0.10 + 0.80 * (0.5 + 0.5 * math.sin(2 * math.pi * t))))
        cy = int(h * (0.10 + 0.80 * (0.5 + 0.5 * math.cos(2 * math.pi * t * 0.61))))
        cx = max(spot_r, min(w - spot_r, cx))
        cy = max(spot_r, min(h - spot_r, cy))
        draw.ellipse([cx - spot_r, cy - spot_r, cx + spot_r, cy + spot_r], fill=205)

    blur_r = max(6, int(min(w, h) * 0.14))
    return mask.filter(ImageFilter.GaussianBlur(radius=blur_r))


def _frontal_creative(w: int, h: int, elapsed_ms: float) -> Image.Image:
    """
    Three animated bright spots orbiting in the anterior (left) portion of the
    frontal lobe, simulating stochastic area-11 activations during creative thought.
    """
    mask = Image.new('L', (w, h), 55)   # low ambient base
    draw = ImageDraw.Draw(mask)

    zone_w = int(w * 0.58)   # confine to anterior (left) portion
    zone_h = h
    spot_r = max(4, int(min(w, h) * 0.11))

    for speed, phase in [(1.0, 0.00), (1.62, 0.33), (0.75, 0.67)]:
        t = (elapsed_ms / 2800.0 * speed + phase) % 1.0
        cx = int(zone_w * (0.15 + 0.70 * (0.5 + 0.5 * math.sin(2 * math.pi * t))))
        cy = int(zone_h * (0.10 + 0.80 * (0.5 + 0.5 * math.cos(2 * math.pi * t * 0.73))))
        cx = max(spot_r, min(w - spot_r, cx))
        cy = max(spot_r, min(h - spot_r, cy))
        draw.ellipse([cx - spot_r, cy - spot_r, cx + spot_r, cy + spot_r], fill=245)

    blur_r = max(3, int(min(w, h) * 0.07))
    return mask.filter(ImageFilter.GaussianBlur(radius=blur_r))
