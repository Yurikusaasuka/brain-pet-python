"""Load brain image layers from img/ using their original artwork.

This loader keeps the user's PNG colors intact, removes the red registration
marker, and strips white paper-like backgrounds so layers can stack cleanly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None  # type: ignore

IMG_DIR = Path(__file__).resolve().parent.parent / "img"

_RED_L, _RED_T, _RED_R, _RED_B = 190, 789, 235, 833

REGION_PATTERNS: dict[str, object] = {
    "pfc_left":   lambda n: ("pfc" in n and "left" in n) or "frontal_left" in n,
    "pfc_right":  lambda n: ("pfc" in n and "right" in n) or "frontal_right" in n,
    "parietal":   lambda n: "parietal" in n,
    "broca":      lambda n: "broca" in n or "language" in n,
    "temporal":   lambda n: "temporal" in n,
    "occipital":  lambda n: "occipital" in n,
    "limbic":     lambda n: "limbic" in n,
    "cerebellum": lambda n: "cerebellum" in n,
    "brainstem":  lambda n: "brainstem" in n or ("stem" in n and "brain" in n),
}


def _strip_red_marker(img: "Image.Image") -> "Image.Image":
    w, h = img.size
    l = max(0, _RED_L)
    t = max(0, _RED_T)
    r = min(w, _RED_R)
    b = min(h, _RED_B)
    if l >= r or t >= b:
        return img

    img = img.copy()
    px = img.load()
    for y in range(t, b):
        for x in range(l, r):
            red, green, blue, alpha = px[x, y]
            if alpha and red > 220 and green < 80 and blue < 80:
                px[x, y] = (0, 0, 0, 0)
    return img


def _strip_white_background(
    img: "Image.Image",
    hard_cutoff: int = 248,
    soft_cutoff: int = 220,
) -> "Image.Image":
    """Remove paper-white backgrounds and soften white fringes.

    Pixels near pure white become transparent. Off-white edge pixels keep some
    alpha so anti-aliased outlines stay smooth instead of turning into white dust.
    """
    img = img.copy().convert("RGBA")
    out = []
    for red, green, blue, alpha in img.getdata():
        if alpha == 0:
            out.append((red, green, blue, 0))
            continue

        lightest = max(red, green, blue)
        darkest = min(red, green, blue)

        if lightest >= hard_cutoff and darkest >= soft_cutoff:
            out.append((red, green, blue, 0))
            continue

        if darkest >= soft_cutoff:
            span = max(1, hard_cutoff - soft_cutoff)
            keep = (hard_cutoff - darkest) / span
            new_alpha = int(alpha * max(0.0, min(1.0, keep)))
            out.append((red, green, blue, new_alpha))
            continue

        out.append((red, green, blue, alpha))

    img.putdata(out)
    return img


def _load_image(path: Path, canvas_size: tuple[int, int], strip_white: bool) -> Optional["Image.Image"]:
    try:
        img = Image.open(path).convert("RGBA")
        img = _strip_red_marker(img)
        if strip_white:
            img = _strip_white_background(img)
        img = img.resize(canvas_size, Image.LANCZOS)
        return img
    except Exception as exc:
        print(f"[brain-pet] Failed to load {path.name}: {exc}")
        return None


def load_layers(target_size: int) -> dict:
    empty = {
        "base": None,
        "frame": None,
        "regions": {},
        "canvas_size": (target_size, target_size),
        "mapping": {},
    }

    if not PIL_AVAILABLE:
        print("[brain-pet] Pillow is not installed. Run: pip install Pillow")
        return empty

    png_files = {f.name: f for f in IMG_DIR.glob("*.png")}
    if not png_files:
        print(f"[brain-pet] No PNG files found in {IMG_DIR}")
        return empty

    ref_name = (
        "brain_1.png" if "brain_1.png" in png_files
        else "brain.png" if "brain.png" in png_files
        else next(iter(png_files))
    )

    try:
        ref = Image.open(png_files[ref_name]).convert("RGBA")
    except Exception as exc:
        print(f"[brain-pet] Cannot open reference {ref_name}: {exc}")
        return empty

    orig_w, orig_h = ref.size
    scale = target_size / max(orig_w, orig_h)
    new_w = max(1, int(orig_w * scale))
    new_h = max(1, int(orig_h * scale))
    canvas_size = (new_w, new_h)

    base = _load_image(png_files["brain.png"], canvas_size, strip_white=True) if "brain.png" in png_files else None
    frame = _load_image(png_files["brain_1.png"], canvas_size, strip_white=True) if "brain_1.png" in png_files else None

    regions: dict[str, "Image.Image"] = {}
    mapping: dict[str, str] = {}

    for fname, fpath in png_files.items():
        stem = Path(fname).stem.lower().replace(" ", "_").replace("-", "_")
        if stem in ("brain", "brain_1"):
            continue

        matched: Optional[str] = None
        for region_id, test in REGION_PATTERNS.items():
            if test(stem):  # type: ignore[operator]
                matched = region_id
                break

        if matched is None and "frontal" in stem:
            img = _load_image(fpath, canvas_size, strip_white=True)
            if img is not None:
                regions["pfc_left"] = img
                regions["pfc_right"] = img
                mapping["pfc_left"] = fname
                mapping["pfc_right"] = fname
            continue

        if matched is not None:
            img = _load_image(fpath, canvas_size, strip_white=True)
            if img is not None:
                regions[matched] = img
                mapping[matched] = fname

    print("[brain-pet] Detected region mapping:")
    if mapping:
        for rid in sorted(mapping):
            print(f"  {rid:12s} -> {mapping[rid]}")
    else:
        print("  (no region layers matched; brain will show base only)")

    return {
        "base": base,
        "frame": frame,
        "regions": regions,
        "canvas_size": canvas_size,
        "mapping": mapping,
    }
