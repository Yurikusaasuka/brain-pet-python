"""Main UI — transparent frameless tkinter window with PIL compositing."""
from __future__ import annotations

import math
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .animation import get_animation_multiplier
from .constants import MANUAL_STATES, WINDOW_SIZES
from .daily_stats import REGION_DISPLAY, check_midnight_reset, update_30s
from .region_effects import get_region_glow_mask
from .region_loader import load_layers
from .settings import load_settings, save_settings
from .state_config import BRAIN_STATES, STATE_VISUAL_BOOST
from .state_machine import BrainState, StateMachine, current_time_overlay
from .tray import TrayIcon

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
TRANSPARENT_COLOR = '#010101'
BUBBLE_PAD_TOP    = 65
STATUS_PAD_BOT    = 28
HORIZ_PAD         = 12


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _try_font(size: int) -> 'ImageFont.ImageFont':
    candidates = [
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/msyhbd.ttc',
        'C:/Windows/Fonts/simhei.ttf',
        'C:/Windows/Fonts/simsun.ttc',
        'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/arial.ttf',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/Helvetica.ttc',
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default(size=size)


@dataclass
class _Drag:
    active: bool = False
    ox: int = 0
    oy: int = 0


# ---------------------------------------------------------------------------
# Compositing
# ---------------------------------------------------------------------------

def _apply_glow(
    img: 'Image.Image',
    intensity: float,
    hex_color: str,
    spatial_mask: Optional['Image.Image'] = None,
) -> 'Image.Image':
    """Render a brain region in hex_color at the given intensity.

    Uses the PNG alpha channel as anatomical shape; colour always comes from
    hex_color so state transitions produce visible colour changes.
    (Previously hex_color was ignored — all states looked identical.)
    """
    effective = max(0.0, min(1.0, intensity))
    if effective <= 0.01:
        invisible = img.copy()
        invisible.putalpha(0)
        return invisible

    try:
        r_c = int(hex_color[1:3], 16)
        g_c = int(hex_color[3:5], 16)
        b_c = int(hex_color[5:7], 16)
    except (ValueError, IndexError):
        r_c, g_c, b_c = 200, 200, 255

    # Shape from PNG alpha
    src_alpha = img.convert('RGBA').split()[3]

    # Apply spatial sub-region mask if present
    if spatial_mask is not None:
        a2 = ImageChops.multiply(src_alpha, spatial_mask)
    else:
        a2 = src_alpha

    # Scale opacity by intensity × animation multiplier
    a2 = a2.point(lambda x: int(x * effective))

    result = Image.new('RGBA', img.size, (r_c, g_c, b_c, 0))
    result.putalpha(a2)

    # Soft bloom at higher intensities
    if effective > 0.5:
        bloom = result.filter(ImageFilter.GaussianBlur(radius=3))
        bloom_alpha = bloom.split()[3].point(lambda x: int(x * 0.24))
        bloom_data = bloom.split()
        bloom = Image.merge('RGBA', (*bloom_data[:3], bloom_alpha))
        result = Image.alpha_composite(bloom, result)

    return result


def _enhance_rgba(
    img: 'Image.Image',
    brightness: float,
    saturation: float,
) -> 'Image.Image':
    """Apply brightness and colour saturation to RGBA while preserving alpha."""
    if brightness == 1.0 and saturation == 1.0:
        return img
    alpha = img.getchannel('A')
    rgb = img.convert('RGB')
    if saturation != 1.0:
        rgb = ImageEnhance.Color(rgb).enhance(saturation)
    if brightness != 1.0:
        rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    result = rgb.convert('RGBA')
    result.putalpha(alpha)
    return result


# ---------------------------------------------------------------------------
# Synthetic region drawing (Broca + Limbic — no PNG files needed)
# ---------------------------------------------------------------------------

def _draw_broca_region(
    img: 'Image.Image',
    intensity: float,
    hex_color: str,
    anim_mult: float = 1.0,
) -> 'Image.Image':
    """Draw Broca area synthetically as a soft ellipse on the frontal-lobe region."""
    if intensity <= 0.0:
        return img
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    eff_intensity = intensity * anim_mult
    alpha = int(255 * eff_intensity * 0.75)
    if alpha <= 0:
        return img
    W, H = img.size
    # Posterior-inferior corner of frontal lobe, sitting on the frontal-temporal boundary.
    # Pixel analysis: at x=80-115 the frontal lobe bottom and temporal lobe top meet at y≈97-131.
    # Center (98, 104) lands exactly on that seam (frontal_bottom=103, temporal_top=102 at x=100).
    bx1 = int(W * 0.28)   # x: ~81 px
    by1 = int(H * 0.35)   # y: ~89 px  (just inside frontal lobe floor)
    bx2 = int(W * 0.40)   # x: ~116 px
    by2 = int(H * 0.48)   # y: ~119 px (just touching temporal lobe top)
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse([bx1, by1, bx2, by2], fill=(r, g, b, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=5))
    return Image.alpha_composite(img, overlay)


def _draw_limbic_region(
    img: 'Image.Image',
    intensity: float,
    hex_color: str,
    anim_mult: float = 1.0,
) -> 'Image.Image':
    """Draw limbic system as a C-shaped arc on the medial brain surface."""
    if intensity <= 0.0:
        return img
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    eff_intensity = intensity * anim_mult
    alpha = int(255 * eff_intensity * 0.75)
    if alpha <= 0:
        return img
    W, H = img.size
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # C-shape: visible left arc spans x 30%–55%, y 35%–60% of brain canvas
    # cx sits at the right cut edge (55%); outer_rx extends left to 30%
    cx = int(W * 0.55)          # right boundary of C (opening faces right)
    cy = int(H * 0.475)         # vertical center: (35+60)/2 = 47.5%
    outer_rx = int(W * 0.25)    # reaches left to 55%-25% = 30%
    outer_ry = int(H * 0.125)   # half of (60%-35%) = 12.5%
    inner_rx = int(W * 0.13)    # ring thickness ~W*0.12 per side
    inner_ry = int(H * 0.07)
    # Draw outer filled ellipse
    draw.ellipse(
        [cx - outer_rx, cy - outer_ry, cx + outer_rx, cy + outer_ry],
        fill=(r, g, b, alpha),
    )
    # Cut out inner ellipse to create ring
    draw.ellipse(
        [cx - inner_rx, cy - inner_ry, cx + inner_rx, cy + inner_ry],
        fill=(0, 0, 0, 0),
    )
    # Cut right half to make C-shape opening rightward
    draw.rectangle(
        [cx, cy - outer_ry - 2, cx + outer_rx + 2, cy + outer_ry + 2],
        fill=(0, 0, 0, 0),
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=7))
    return Image.alpha_composite(img, overlay)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class BrainPetApp:
    def __init__(self) -> None:
        self.settings = load_settings()

        # --- tkinter root ---
        self.root = tk.Tk()
        self.root.title('Brain Pet')
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        try:
            self.root.wm_attributes('-transparentcolor', TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        self.root.attributes('-alpha', self.settings.get('opacity', 0.98))

        # --- Load PIL layers ---
        size_key = self.settings.get('brain_size', 'M')
        target_px = WINDOW_SIZES.get(size_key, 290)
        self._layers = load_layers(target_px)
        bw, bh = self._layers['canvas_size']

        self._brain_x = HORIZ_PAD
        self._brain_y = BUBBLE_PAD_TOP
        self._win_w   = bw + HORIZ_PAD * 2
        self._win_h   = bh + BUBBLE_PAD_TOP + STATUS_PAD_BOT

        # --- Canvas ---
        self.canvas = tk.Canvas(
            self.root,
            width=self._win_w,
            height=self._win_h,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()

        self._brain_photo: Optional['ImageTk.PhotoImage'] = None
        self._brain_canvas_item: Optional[int] = None

        # --- Fonts ---
        self._font_bubble = _try_font(11)
        self._font_status = _try_font(9)

        # --- Animation state ---
        self._start_ms = time.monotonic() * 1000.0
        self._anim_enabled = self.settings.get('animation_enabled', True)

        # --- Speech bubble state ---
        self._bubble_text: Optional[str] = None
        self._bubble_until: float = 0.0
        self._bubble_after_id: Optional[str] = None

        # --- Video question widgets ---
        self._video_btn_ids: list[int] = []
        self._video_btns: list[tk.Button] = []

        # --- Pomodoro phase overlay widgets ---
        self._pom_btn_ids: list[int] = []
        self._pom_btns: list[tk.Button] = []
        self._pom_phase_shown: str = ''   # phase currently reflected in UI

        # --- Drag ---
        self._drag = _Drag()

        # --- State machine ---
        self._sm = StateMachine(self.settings)
        self._current_state_id = 'IDLE'

        # --- Tray ---
        self._tray = TrayIcon(self)

        # Dopamine crash transition
        self._dopamine_trans_frames: int = 0
        self._dopamine_limbic_override: Optional[float] = None

        check_midnight_reset(self.settings)

        self._place_window(size_key)
        self._bind_events()
        self._build_menu()

        self._sm.start()
        self._tray.start()

        self.root.after(30000, self._do_stats_tick)
        self._animate()

    # ------------------------------------------------------------------
    # Window placement
    # ------------------------------------------------------------------

    def _place_window(self, size_key: str) -> None:
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = self.settings.get('x')
        y = self.settings.get('y')
        if x is None or y is None:
            x = sw - self._win_w - 32
            y = sh - self._win_h - 72
        self.root.geometry(f'{self._win_w}x{self._win_h}+{int(x)}+{int(y)}')

    # ------------------------------------------------------------------
    # Event binding
    # ------------------------------------------------------------------

    def _bind_events(self) -> None:
        self.canvas.bind('<ButtonPress-1>',   self._drag_start)
        self.canvas.bind('<B1-Motion>',       self._drag_motion)
        self.canvas.bind('<ButtonRelease-1>', self._drag_end)
        self.canvas.bind('<Button-3>',        self._show_menu)

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        self._menu = tk.Menu(self.root, tearoff=False)
        self._video_menu = tk.Menu(self._menu, tearoff=False)
        self._video_menu.add_command(label='📚 纪录片 / 学习',
                                     command=lambda: self._sm.answer_video('DOCUMENTARY'))
        self._video_menu.add_command(label='🎭 娱乐',
                                     command=lambda: self._sm.answer_video('ENTERTAINMENT'))
        self._video_menu.add_command(label='😱 恐怖 / 惊悚',
                                     command=lambda: self._sm.answer_video('HORROR'))
        self._video_menu.add_command(label='🎮 游戏',
                                     command=lambda: self._sm.answer_video('GAMING'))

    def _show_menu(self, event: tk.Event) -> None:
        self._menu.delete(0, 'end')
        self._menu.add_command(label='🏃 运动中',
                               command=lambda: self.set_manual_state('EXERCISE'))
        self._menu.add_command(label='🍜 用餐中',
                               command=lambda: self.set_manual_state('EATING'))
        self._menu.add_command(label='😴 去睡觉',
                               command=lambda: self.set_manual_state('SLEEPING'))
        self._menu.add_command(label='🚶 散步中',
                               command=lambda: self.set_manual_state('WALKING'))
        self._menu.add_command(label='💡 创意模式',
                               command=lambda: self.set_manual_state('CREATIVE'))
        self._menu.add_command(label='↩ 回到初始状态',
                               command=lambda: self.set_manual_state(None))
        self._menu.add_separator()
        if self._current_state_id == 'VIDEO_UNKNOWN':
            self._menu.add_cascade(label='视频类型', menu=self._video_menu)
            self._menu.add_separator()
        self._menu.add_command(label='🔽 隐藏到托盘', command=self._hide_to_tray)
        self._menu.add_separator()
        self._menu.add_command(label='📊 今日大脑报告', command=self._open_stats_panel)
        self._menu.add_command(label='🍅 番茄钟设置', command=self._open_pomodoro_settings)
        self._menu.add_command(label='⚙ 设置', command=self._open_settings)
        self._menu.add_command(label='❌ 退出', command=self.close)
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------

    def _drag_start(self, event: tk.Event) -> None:
        self._drag.active = True
        self._drag.ox = event.x_root - self.root.winfo_x()
        self._drag.oy = event.y_root - self.root.winfo_y()

    def _drag_motion(self, event: tk.Event) -> None:
        if not self._drag.active:
            return
        x = event.x_root - self._drag.ox
        y = event.y_root - self._drag.oy
        self.root.geometry(f'+{x}+{y}')

    def _drag_end(self, _: tk.Event) -> None:
        if not self._drag.active:
            return
        self._drag.active = False
        self.settings['x'] = self.root.winfo_x()
        self.settings['y'] = self.root.winfo_y()
        save_settings(self.settings)

    # ------------------------------------------------------------------
    # Public state control
    # ------------------------------------------------------------------

    def set_manual_state(self, state_id: Optional[str]) -> None:
        self._sm.set_manual(state_id)
        self.settings['manual_state'] = state_id
        save_settings(self.settings)

    def _hide_to_tray(self) -> None:
        self.root.withdraw()

    def close(self) -> None:
        self.settings['x'] = self.root.winfo_x()
        self.settings['y'] = self.root.winfo_y()
        save_settings(self.settings)
        self._sm.stop()
        self._tray.stop()
        self.root.destroy()

    # ------------------------------------------------------------------
    # Auto-hide logic
    # ------------------------------------------------------------------

    def _check_auto_hide(self) -> None:
        snap = self._sm.last_snap
        hide = False
        if self.settings.get('hide_on_game') and self._current_state_id == 'GAMING':
            hide = True
        elif (self.settings.get('hide_on_fullscreen_video')
              and snap is not None and snap.is_fullscreen
              and 'VIDEO' in self._current_state_id):
            hide = True

        if hide:
            if self.root.state() != 'withdrawn':
                self.root.withdraw()
        else:
            if self.root.state() == 'withdrawn':
                self.root.deiconify()

    # ------------------------------------------------------------------
    # Animation loop (30 fps)
    # ------------------------------------------------------------------

    def _animate(self) -> None:
        self._current_state_id = self._sm.update()

        # Pending one-time bubble
        pending_msg = self._sm.get_pending_bubble()
        if pending_msg:
            self.show_bubble(pending_msg, duration_ms=4000)

        # Dopamine crash: start fade transition on first entry
        if self._current_state_id == 'DOPAMINE_CRASH' and self._sm.pop_dopamine_entered():
            self._dopamine_trans_frames = 90
            self._dopamine_limbic_override = 0.9

        # Show / hide video question
        if self._sm.pending_video_question and not self._video_btns:
            self._show_video_question()
        elif not self._sm.pending_video_question and self._video_btns:
            self._hide_video_question()

        # Pomodoro phase overlay: update buttons when phase changes
        pom_phase = self._sm.pom_phase
        if pom_phase != self._pom_phase_shown:
            self._hide_pom_prompt()
            if pom_phase == 'WORK_DONE':
                cfg = self.settings.get('pomodoro', {})
                break_min = cfg.get('break_minutes', 5)
                self._show_pom_prompt(f'🛁 开始休息 {break_min} 分钟', self._sm.pom_confirm_break)
            elif pom_phase == 'REST_DONE':
                self._show_pom_prompt('💪 重新开始工作', self._sm.pom_confirm_work)
            self._pom_phase_shown = pom_phase

        # Auto-hide for gaming / fullscreen
        self._check_auto_hide()

        # Compose and update canvas — wrapped so a draw error never breaks the loop
        if PIL_AVAILABLE:
            try:
                self._composite_and_update()
            except Exception:
                pass

        # Update tray
        state = BRAIN_STATES.get(self._current_state_id, BRAIN_STATES['IDLE'])
        self._tray.update(state.get('primary_color', '#3498DB'), state.get('name', ''))

        self.root.after(33, self._animate)

    # ------------------------------------------------------------------
    # Compositing
    # ------------------------------------------------------------------

    def _composite_and_update(self) -> None:
        elapsed_ms = time.monotonic() * 1000.0 - self._start_ms

        state = BRAIN_STATES.get(self._current_state_id, BRAIN_STATES['IDLE'])
        anim_style = state.get('animation', 'static') if self._anim_enabled else 'static'
        pulse_ms   = state.get('pulse_speed', 2000)
        mult = get_animation_multiplier(anim_style, pulse_ms, elapsed_ms)

        brain_state = BrainState(state)
        brain_state.set_mult(mult)

        overlay = current_time_overlay()
        brightness = overlay.get('brightness', 1.0)

        # Dopamine crash fade transition
        intensity_overrides: dict[str, float] = {}
        if self._current_state_id == 'DOPAMINE_CRASH':
            if self._dopamine_trans_frames > 0:
                progress = 1.0 - self._dopamine_trans_frames / 90.0
                self._dopamine_limbic_override = 0.9 - (0.9 - 0.08) * progress
                self._dopamine_trans_frames -= 1
            if self._dopamine_limbic_override is not None:
                intensity_overrides['limbic'] = self._dopamine_limbic_override
        else:
            self._dopamine_trans_frames = 0
            self._dopamine_limbic_override = None

        full = Image.new('RGBA', (self._win_w, self._win_h), (0, 0, 0, 0))

        brain_img = self._composite_brain(brain_state, elapsed_ms, intensity_overrides, mult)
        if brain_img is not None:
            boost_b, boost_s = STATE_VISUAL_BOOST.get(self._current_state_id, (1.0, 1.0))
            brain_img = _enhance_rgba(brain_img, boost_b, boost_s)

            # Skip brightness overlay for OVERLOAD and FLOW_STATE
            if brightness != 1.0 and self._current_state_id not in ('OVERLOAD', 'FLOW_STATE'):
                brain_img = _enhance_rgba(brain_img, brightness, 1.0)

            # Afternoon drowsy warm micro-pulse (12–14 h)
            if overlay.get('drowsy') and self._current_state_id not in ('OVERLOAD', 'FLOW_STATE'):
                t = (elapsed_ms % 6000.0) / 6000.0
                drowsy_alpha = int(12 * (math.sin(math.pi * t) ** 2))
                if drowsy_alpha > 0:
                    tint = Image.new('RGBA', brain_img.size, (255, 190, 80, drowsy_alpha))
                    brain_img = Image.alpha_composite(brain_img, tint)

            full.paste(brain_img, (self._brain_x, self._brain_y), brain_img)

        # Gold crown for FOCUS_STREAK
        if self._current_state_id == 'FOCUS_STREAK':
            self._draw_crown(full)

        self._draw_status(full, state, overlay)

        bubble_text = self._current_bubble_text()
        if bubble_text and self.settings.get('bubble_enabled', True):
            self._draw_bubble(full, bubble_text)

        photo = ImageTk.PhotoImage(full)
        self._brain_photo = photo

        if self._brain_canvas_item is None:
            self._brain_canvas_item = self.canvas.create_image(0, 0, anchor='nw', image=photo)
        else:
            self.canvas.itemconfig(self._brain_canvas_item, image=photo)

    def _composite_brain(
        self, brain_state: BrainState, elapsed_ms: float,
        intensity_overrides: Optional[dict] = None,
        anim_mult: float = 1.0,
    ) -> Optional['Image.Image']:
        bw, bh = self._layers['canvas_size']
        result = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))

        base = self._layers['base']
        if base is not None:
            result = Image.alpha_composite(result, base)

        # Deduplicate: pfc_left and pfc_right may share the same image file.
        seen: dict[int, tuple[str, float, str, Optional[str], 'Image.Image']] = {}
        for region_id, layer_img in self._layers['regions'].items():
            intensity = brain_state.get_intensity(region_id)
            img_id = id(layer_img)
            if img_id not in seen or intensity > seen[img_id][1]:
                seen[img_id] = (
                    region_id,
                    intensity,
                    brain_state.get_color(region_id),
                    brain_state.get_effect(region_id),
                    layer_img,
                )

        for region_id, intensity, color, effect, layer_img in seen.values():
            if intensity_overrides and region_id in intensity_overrides:
                intensity = intensity_overrides[region_id]
            if intensity > 0.01:
                w, h = layer_img.size
                mask = get_region_glow_mask(region_id, effect, w, h, elapsed_ms)
                visible_layer = _apply_glow(layer_img, intensity, color, mask)
                result = Image.alpha_composite(result, visible_layer)

        # Draw Broca area synthetically (no PNG)
        broca_intensity = brain_state.get_intensity('broca')
        if intensity_overrides and 'broca' in intensity_overrides:
            broca_intensity = intensity_overrides['broca']
        if broca_intensity > 0.01:
            result = _draw_broca_region(result, broca_intensity,
                                        brain_state.get_color('broca'), anim_mult)

        # Draw Limbic region synthetically (no PNG)
        limbic_intensity = brain_state.get_intensity('limbic')
        if intensity_overrides and 'limbic' in intensity_overrides:
            limbic_intensity = intensity_overrides['limbic']
        if limbic_intensity > 0.01:
            result = _draw_limbic_region(result, limbic_intensity,
                                         brain_state.get_color('limbic'), anim_mult)

        frame = self._layers['frame']
        if frame is not None:
            result = Image.alpha_composite(result, frame)

        return result

    # ------------------------------------------------------------------
    # Bubble
    # ------------------------------------------------------------------

    def show_bubble(self, text: str, duration_ms: int = 4000) -> None:
        self._bubble_text = text
        self._bubble_until = time.monotonic() + duration_ms / 1000.0
        if self._bubble_after_id is not None:
            self.root.after_cancel(self._bubble_after_id)
        self._bubble_after_id = self.root.after(duration_ms, self._clear_bubble)

    def _clear_bubble(self) -> None:
        self._bubble_text = None
        self._bubble_after_id = None

    def _current_bubble_text(self) -> Optional[str]:
        if self._bubble_text and time.monotonic() < self._bubble_until:
            return self._bubble_text
        return None

    def _draw_bubble(self, canvas_img: 'Image.Image', text: str) -> None:
        draw = ImageDraw.Draw(canvas_img)
        cx = self._win_w // 2

        try:
            bbox = draw.textbbox((0, 0), text, font=self._font_bubble)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = len(text) * 7, 14

        bw = max(140, tw + 32)
        bh = th + 20
        x1 = cx - bw // 2
        y2 = self._brain_y - 8
        y1 = y2 - bh
        x2 = cx + bw // 2

        x1 = max(4, x1); x2 = min(self._win_w - 4, x2)
        y1 = max(4, y1)

        draw.rounded_rectangle(
            [x1, y1, x2, y2],
            radius=12,
            fill=(240, 248, 255, 215),
            outline=(160, 200, 240, 200),
            width=2,
        )
        tail = [(cx - 6, y2 - 1), (cx + 6, y2 - 1), (cx, y2 + 10)]
        draw.polygon(tail, fill=(240, 248, 255, 215))
        draw.text(
            (cx, (y1 + y2) // 2),
            text,
            fill=(30, 60, 100, 255),
            font=self._font_bubble,
            anchor='mm',
        )

    def _draw_status(self, canvas_img: 'Image.Image', state: dict, overlay: dict) -> None:
        draw = ImageDraw.Draw(canvas_img)
        snap = self._sm.last_snap
        ai_tag = ''
        if snap is not None and snap.is_ai and state.get('id') in ('WRITING', 'NORMAL_WORK', 'DEEP_FOCUS'):
            ai_tag = ' · AI协作'

        # Pomodoro phase indicator appended to status bar
        pom_tag = ''
        pom_phase = self._sm.pom_phase
        if pom_phase == 'WORK':
            elapsed = self._sm.pom_work_elapsed_seconds
            cfg = self.settings.get('pomodoro', {})
            target_secs = cfg.get('work_minutes', 25) * 60
            if elapsed >= target_secs * 0.5:
                m, s = int(elapsed // 60), int(elapsed % 60)
                pom_tag = f'  · 🍅 {m:02d}:{s:02d}'
        elif pom_phase == 'WORK_DONE':
            pom_tag = '  · ✅ 可以休息啦'
        elif pom_phase == 'REST':
            rem = self._sm.pom_rest_remaining_seconds
            m, s = int(rem // 60), int(rem % 60)
            pom_tag = f'  · 😴 {m:02d}:{s:02d}'
        elif pom_phase == 'REST_DONE':
            pom_tag = '  · 💪 可以继续了'

        label = f"{state['name']}{ai_tag}  ·  {overlay['name']}{pom_tag}"
        cx = self._win_w // 2
        sy = self._brain_y + self._layers['canvas_size'][1] + STATUS_PAD_BOT // 2

        try:
            bbox = draw.textbbox((0, 0), label, font=self._font_status)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = len(label) * 6, 12

        bw = tw + 28
        bh = th + 12
        x1 = cx - bw // 2
        x2 = cx + bw // 2
        y1 = sy - bh // 2
        y2 = sy + bh // 2

        draw.rounded_rectangle([x1, y1, x2, y2], radius=8, fill=(20, 40, 70, 180))
        draw.text((cx, sy), label, fill=(220, 240, 255, 255),
                  font=self._font_status, anchor='mm')

    # ------------------------------------------------------------------
    # Video question buttons (Chinese)
    # ------------------------------------------------------------------

    def _show_video_question(self) -> None:
        if self._video_btns:
            return
        labels = [
            ('📚 纪录片', 'DOCUMENTARY'),
            ('🎭 娱乐',   'ENTERTAINMENT'),
            ('😱 恐怖',   'HORROR'),
            ('🎮 游戏',   'GAMING'),
        ]
        cx = self._win_w // 2
        start_y = self._brain_y - 4
        btn_h = 24
        gap = 3
        total = len(labels) * (btn_h + gap)
        y = start_y - total

        for label, subtype in labels:
            btn = tk.Button(
                self.canvas,
                text=label,
                font=('Microsoft YaHei', 9),
                bg='#2C3E50',
                fg='#ECF0F1',
                activebackground='#34495E',
                activeforeground='#FFFFFF',
                relief='flat',
                bd=0,
                padx=8,
                pady=2,
                cursor='hand2',
                command=lambda st=subtype: self._answer_video(st),
            )
            cid = self.canvas.create_window(cx, y + btn_h // 2, window=btn, anchor='center')
            self._video_btns.append(btn)
            self._video_btn_ids.append(cid)
            y += btn_h + gap

    def _answer_video(self, subtype: str) -> None:
        self._sm.answer_video(subtype)
        self._hide_video_question()

    def _hide_video_question(self) -> None:
        for cid in self._video_btn_ids:
            try:
                self.canvas.delete(cid)
            except Exception:
                pass
        for btn in self._video_btns:
            try:
                btn.destroy()
            except Exception:
                pass
        self._video_btns.clear()
        self._video_btn_ids.clear()

    # ------------------------------------------------------------------
    # Pomodoro phase overlay (confirm buttons)
    # ------------------------------------------------------------------

    def _show_pom_prompt(self, label_text: str, callback) -> None:
        """Show a single action button above the brain for pomodoro phase transitions."""
        if self._pom_btns:
            return
        cx = self._win_w // 2
        # Place just above the brain image, below the bubble area
        y = self._brain_y - 6
        btn = tk.Button(
            self.canvas,
            text=label_text,
            font=('Microsoft YaHei', 10, 'bold'),
            bg='#1A5276',
            fg='#FDFEFE',
            activebackground='#2E86C1',
            activeforeground='#FFFFFF',
            relief='flat',
            bd=0,
            padx=12,
            pady=4,
            cursor='hand2',
            command=lambda: self._on_pom_click(callback),
        )
        cid = self.canvas.create_window(cx, y, window=btn, anchor='s')
        self._pom_btns.append(btn)
        self._pom_btn_ids.append(cid)

    def _on_pom_click(self, callback) -> None:
        callback()
        self._hide_pom_prompt()
        self._pom_phase_shown = ''   # force re-evaluation next frame

    def _hide_pom_prompt(self) -> None:
        for cid in self._pom_btn_ids:
            try:
                self.canvas.delete(cid)
            except Exception:
                pass
        for btn in self._pom_btns:
            try:
                btn.destroy()
            except Exception:
                pass
        self._pom_btns.clear()
        self._pom_btn_ids.clear()

    # ------------------------------------------------------------------
    # Settings window (FIX 2: integer sliders)
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title('Brain Pet – 设置')
        win.resizable(False, False)
        win.grab_set()

        try:
            import tkinter.ttk as ttk
        except ImportError:
            ttk = tk  # type: ignore

        pad = {'padx': 10, 'pady': 4}

        # --- Work apps ---
        tk.Label(win, text='工作应用名称（每行一个）:', anchor='w').grid(
            row=0, column=0, columnspan=3, sticky='w', **pad)
        apps_box = tk.Text(win, width=30, height=8, font=('Consolas', 9))
        apps_box.grid(row=1, column=0, columnspan=3, **pad)
        apps_box.insert('1.0', '\n'.join(self.settings.get('work_apps', [])))

        # Integer sliders using tk.Scale with resolution=1
        def _int_slider_row(row, label, key, lo, hi, default):
            tk.Label(win, text=label).grid(row=row, column=0, sticky='w', **pad)
            var = tk.IntVar(value=int(self.settings.get(key, default)))
            sl = tk.Scale(
                win, from_=lo, to=hi, resolution=1, orient=tk.HORIZONTAL,
                variable=var, length=150, showvalue=False,
                command=lambda v: var.set(int(float(v))),
            )
            sl.grid(row=row, column=1, sticky='ew', **pad)
            lbl = tk.Label(win, textvariable=var, width=4)
            lbl.grid(row=row, column=2, sticky='w')
            return var

        focus_var = _int_slider_row(2, '深度专注阈值 (分钟)', 'focus_threshold', 5, 60, 20)
        rest_var  = _int_slider_row(3, '休息检测阈值 (分钟)', 'rest_threshold',  1, 30,  5)
        owc_var   = _int_slider_row(4, '过载窗口数阈值',      'overload_window_count', 3, 30, 10)

        # --- Toggles ---
        def _toggle_row(row, label, key, default):
            var = tk.BooleanVar(value=self.settings.get(key, default))
            cb = ttk.Checkbutton(win, text=label, variable=var)
            cb.grid(row=row, column=0, columnspan=3, sticky='w', **pad)
            return var

        vq_var   = _toggle_row(5, '看视频时询问类型',       'video_question_enabled',   True)
        fa_var   = _toggle_row(6, '心流状态提醒',           'flow_alert_enabled',        True)
        ln_var   = _toggle_row(7, '深夜提醒',               'late_night_reminder_enabled', True)
        bub_var  = _toggle_row(8, '显示气泡提示',           'bubble_enabled',             True)
        anim_var = _toggle_row(9, '启用动画',               'animation_enabled',          True)
        hg_var   = _toggle_row(10, '打开游戏时自动隐藏桌宠', 'hide_on_game',              False)
        hv_var   = _toggle_row(11, '全屏视频时自动隐藏桌宠', 'hide_on_fullscreen_video',  False)

        # --- Size ---
        tk.Label(win, text='大脑尺寸:').grid(row=12, column=0, sticky='w', **pad)
        size_var = tk.StringVar(value=self.settings.get('brain_size', 'M'))
        for col, sz in enumerate(['S', 'M', 'L']):
            ttk.Radiobutton(win, text=sz, variable=size_var, value=sz).grid(
                row=12, column=col + 1, sticky='w', padx=2)

        # --- Save ---
        def _save():
            self.settings['work_apps'] = [
                ln.strip() for ln in apps_box.get('1.0', 'end').splitlines() if ln.strip()
            ]
            self.settings['focus_threshold']        = int(focus_var.get())
            self.settings['rest_threshold']         = int(rest_var.get())
            self.settings['overload_window_count']  = int(owc_var.get())
            self.settings['video_question_enabled'] = vq_var.get()
            self.settings['flow_alert_enabled']     = fa_var.get()
            self.settings['late_night_reminder_enabled'] = ln_var.get()
            self.settings['bubble_enabled']         = bub_var.get()
            self.settings['animation_enabled']      = anim_var.get()
            self.settings['hide_on_game']           = hg_var.get()
            self.settings['hide_on_fullscreen_video'] = hv_var.get()
            self._anim_enabled = anim_var.get()
            new_size = size_var.get()
            if new_size != self.settings.get('brain_size'):
                self.settings['brain_size'] = new_size
                self._reload_layers(new_size)
            save_settings(self.settings)
            win.destroy()

        ttk.Button(win, text='保存', command=_save).grid(
            row=13, column=0, columnspan=3, pady=8)

    # ------------------------------------------------------------------
    # Pomodoro settings panel (FIX 9)
    # ------------------------------------------------------------------

    def _open_pomodoro_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title('🍅 番茄钟设置')
        win.geometry('340x300')
        win.resizable(False, False)
        win.grab_set()

        try:
            import tkinter.ttk as ttk
        except ImportError:
            ttk = tk  # type: ignore

        FONT = 'Microsoft YaHei'
        pom = self.settings.get('pomodoro', {})
        pad = {'padx': 14, 'pady': 5}

        tk.Label(win, text='🍅 番茄钟设置', font=(FONT, 12, 'bold')).pack(pady=(10, 4))
        ttk.Separator(win).pack(fill='x', padx=12, pady=(0, 6))

        frame = tk.Frame(win)
        frame.pack(fill='x', padx=12)

        def _pom_slider(row, label, key, lo, hi, default, unit='分钟'):
            tk.Label(frame, text=label, font=(FONT, 9), width=14, anchor='w').grid(
                row=row, column=0, sticky='w', **pad)
            var = tk.IntVar(value=int(pom.get(key, default)))
            sl = tk.Scale(
                frame, from_=lo, to=hi, resolution=1, orient=tk.HORIZONTAL,
                variable=var, length=120, showvalue=False,
                command=lambda v: var.set(int(float(v))),
            )
            sl.grid(row=row, column=1, sticky='ew', **pad)
            lbl_var = tk.StringVar(value=f'{var.get()} {unit}')
            def _update(v, lv=lbl_var, sv=var, u=unit):
                sv.set(int(float(v)))
                lv.set(f'{sv.get()} {u}')
            sl.configure(command=_update)
            tk.Label(frame, textvariable=lbl_var, font=(FONT, 9), width=6).grid(
                row=row, column=2, sticky='w')
            return var

        work_var   = _pom_slider(0, '工作时长',   'work_minutes',    10, 60, 25)
        wtol_var   = _pom_slider(1, '误差范围',    'work_tolerance',   1,  5,  2)
        break_var  = _pom_slider(2, '短休息时长',  'break_minutes',    1, 15,  5)
        btol_var   = _pom_slider(3, '休息误差',    'break_tolerance',  1,  3,  1)
        streak_var = _pom_slider(4, '连胜触发数',  'streak_threshold', 2, 10,  3, '个')

        ttk.Separator(win).pack(fill='x', padx=12, pady=(6, 0))
        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=8)

        def _save():
            self.settings['pomodoro'] = {
                'work_minutes':    int(work_var.get()),
                'work_tolerance':  int(wtol_var.get()),
                'break_minutes':   int(break_var.get()),
                'break_tolerance': int(btol_var.get()),
                'streak_threshold': int(streak_var.get()),
            }
            save_settings(self.settings)
            win.destroy()

        def _reset():
            for var, default in [(work_var, 25), (wtol_var, 2), (break_var, 5),
                                  (btol_var, 1), (streak_var, 3)]:
                var.set(default)

        ttk.Button(btn_frame, text='保存', command=_save).pack(side='left', padx=6)
        ttk.Button(btn_frame, text='重置默认', command=_reset).pack(side='left', padx=6)
        ttk.Button(btn_frame, text='关闭', command=win.destroy).pack(side='left', padx=6)

    # ------------------------------------------------------------------
    # 30-second stats accumulation tick
    # ------------------------------------------------------------------

    def _do_stats_tick(self) -> None:
        state = BRAIN_STATES.get(self._current_state_id, BRAIN_STATES['IDLE'])
        intensities = {
            rid: data.get('intensity', 0.0)
            for rid, data in state.get('regions', {}).items()
            if data.get('intensity', 0.0) > 0.01
        }
        switches_30s = 0
        snap = self._sm.last_snap
        if snap is not None:
            now_m = time.monotonic()
            switches_30s = len([t for t in snap.recent_switches if now_m - t <= 32.0])

        update_30s(
            self.settings,
            self._current_state_id,
            intensities,
            switches_30s,
            self._sm.current_focus_minutes,
        )
        save_settings(self.settings)
        self.root.after(30000, self._do_stats_tick)

    # ------------------------------------------------------------------
    # Gold crown for FOCUS_STREAK
    # ------------------------------------------------------------------

    def _draw_crown(self, full_img: 'Image.Image') -> None:
        draw = ImageDraw.Draw(full_img)
        cx = self._win_w // 2
        y_top = self._brain_y - 22
        for dx in (-20, 0, 20):
            x = cx + dx
            draw.polygon(
                [(x - 8, y_top + 16), (x + 8, y_top + 16), (x, y_top)],
                fill='#FFD700',
            )

    # ------------------------------------------------------------------
    # Daily stats panel (FIX 9: removed sleep tracking, added first_activation)
    # ------------------------------------------------------------------

    def _open_stats_panel(self) -> None:
        import tkinter.ttk as ttk

        check_midnight_reset(self.settings)
        ds = self.settings.get('daily_stats') or {}

        win = tk.Toplevel(self.root)
        win.title('今日大脑报告')
        win.geometry('500x430')
        win.resizable(False, False)
        win.configure(bg='#FAFAFA')
        win.attributes('-topmost', False)

        FONT = 'Microsoft YaHei'
        today = ds.get('date', '—')
        first_act = ds.get('first_activation_time', '—')

        # Header
        hdr = tk.Frame(win, bg='#FAFAFA')
        hdr.pack(fill='x', padx=16, pady=(12, 4))
        tk.Label(hdr, text='🧠 今日大脑报告', font=(FONT, 14, 'bold'),
                 bg='#FAFAFA', fg='#2C3E50').pack(side='left')
        tk.Label(hdr, text=today, font=(FONT, 11),
                 bg='#FAFAFA', fg='#7F8C8D').pack(side='right', padx=4)
        ttk.Separator(win).pack(fill='x', padx=16, pady=(0, 4))

        # Region bars
        ri = ds.get('region_intensity_sum', {})
        visible: list[tuple[str, str, str, float]] = []
        seen_names: set[str] = set()
        for rid in self._layers.get('regions', {}):
            name, color = REGION_DISPLAY.get(rid, (rid, '#3498DB'))
            if name in seen_names:
                continue
            seen_names.add(name)
            val = ri.get(rid, 0.0)
            visible.append((rid, name, color, val))
        visible.sort(key=lambda x: -x[3])
        max_val = max((v for *_, v in visible), default=0.0) or 1.0

        bar_frame = tk.Frame(win, bg='#FAFAFA')
        bar_frame.pack(fill='x', padx=16, pady=4)

        if visible:
            BAR_W = 200
            for i, (rid, name, color, val) in enumerate(visible[:5]):
                pct = val / max_val
                row = tk.Frame(bar_frame, bg='#FAFAFA')
                row.pack(fill='x', pady=2)
                prefix = '最活跃脑区：' if i == 0 else '            '
                tk.Label(row, text=f'{prefix}{name}', font=(FONT, 9),
                         bg='#FAFAFA', fg='#2C3E50', width=14, anchor='w').pack(side='left')
                c = tk.Canvas(row, width=BAR_W, height=16, bg='#FAFAFA', highlightthickness=0)
                c.pack(side='left', padx=6)
                c.create_rectangle(0, 0, BAR_W, 16, fill='#E8E8E8', outline='')
                filled = max(2, int(BAR_W * pct))
                c.create_rectangle(0, 0, filled, 16, fill=color, outline='')
                tk.Label(row, text=f'{int(pct*100)}%', font=(FONT, 9),
                         bg='#FAFAFA', fg='#7F8C8D', width=5).pack(side='left')
        else:
            tk.Label(bar_frame, text='暂无数据', font=(FONT, 10),
                     bg='#FAFAFA', fg='#95A5A6').pack()

        ttk.Separator(win).pack(fill='x', padx=16, pady=(4, 4))

        # Stats summary
        def _fmt(mins: float) -> str:
            h, m = int(mins // 60), int(mins % 60)
            return f'{h}小时{m}分钟' if h else f'{m}分钟'

        total_focus = ds.get('total_focus_minutes', 0.0)
        longest     = ds.get('longest_focus_minutes', 0.0)
        pomodoros   = ds.get('pomodoro_count', 0)
        switches    = ds.get('window_switches', 0)

        rows = [
            ('专注时长',     _fmt(total_focus)),
            ('最长连续专注', _fmt(longest)),
            (f'番茄钟完成',  f'{pomodoros} 🍅'),
            ('应用切换',     f'{switches} 次'),
        ]
        sf = tk.Frame(win, bg='#FAFAFA')
        sf.pack(fill='x', padx=24, pady=4)
        for i, (label, value) in enumerate(rows):
            col, row_n = i % 2, i // 2
            f2 = tk.Frame(sf, bg='#FAFAFA')
            f2.grid(row=row_n, column=col, sticky='w', padx=(0, 30), pady=3)
            tk.Label(f2, text=f'{label}：', font=(FONT, 9),
                     bg='#FAFAFA', fg='#7F8C8D').pack(side='left')
            tk.Label(f2, text=value, font=(FONT, 10, 'bold'),
                     bg='#FAFAFA', fg='#2C3E50').pack(side='left')

        ttk.Separator(win).pack(fill='x', padx=16, pady=(4, 4))

        # State distribution bar
        tk.Label(win, text='今日状态分布', font=(FONT, 9),
                 bg='#FAFAFA', fg='#7F8C8D', anchor='w').pack(fill='x', padx=16)

        sm_data = ds.get('state_minutes', {})
        total_mins = sum(sm_data.values())
        dist = tk.Canvas(win, width=464, height=26, bg='#FAFAFA', highlightthickness=0)
        dist.pack(padx=16, pady=4)

        if total_mins > 0:
            items = sorted(
                [(sid, m) for sid, m in sm_data.items() if m >= 0.5],
                key=lambda x: -x[1],
            )
            x = 0
            for sid, m in items:
                w = max(1, int(464 * m / total_mins))
                color = BRAIN_STATES.get(sid, {}).get('primary_color', '#3498DB')
                dist.create_rectangle(x, 0, x + w, 22, fill=color, outline='white', width=1)
                if w > 38:
                    name = BRAIN_STATES.get(sid, {}).get('name', sid)
                    dist.create_text(x + w // 2, 11, text=name,
                                     font=(FONT, 7), fill='white')
                x += w
        else:
            dist.create_text(232, 13, text='暂无数据', font=(FONT, 10), fill='#95A5A6')

        ttk.Separator(win).pack(fill='x', padx=16, pady=(4, 4))

        # First activation time (replaces sleep tracking)
        sf2 = tk.Frame(win, bg='#FAFAFA')
        sf2.pack(fill='x', padx=24, pady=(2, 6))
        tk.Label(sf2, text='今日首次激活时间：', font=(FONT, 9),
                 bg='#FAFAFA', fg='#7F8C8D').pack(side='left')
        tk.Label(sf2, text=first_act, font=(FONT, 10, 'bold'),
                 bg='#FAFAFA', fg='#2C3E50').pack(side='left')

        tk.Button(win, text='关闭', font=(FONT, 10), bg='#ECF0F1',
                  relief='flat', padx=20, pady=6, command=win.destroy).pack(pady=(4, 10))

    def _reload_layers(self, size_key: str) -> None:
        target_px = WINDOW_SIZES.get(size_key, 290)
        self._layers = load_layers(target_px)
        bw, bh = self._layers['canvas_size']
        self._win_w = bw + HORIZ_PAD * 2
        self._win_h = bh + BUBBLE_PAD_TOP + STATUS_PAD_BOT
        self.canvas.config(width=self._win_w, height=self._win_h)
        self.root.geometry(
            f'{self._win_w}x{self._win_h}'
            f'+{self.root.winfo_x()}+{self.root.winfo_y()}'
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    if not PIL_AVAILABLE:
        print('[brain-pet] ERROR: Pillow is required. Run: pip install Pillow')
        return
    app = BrainPetApp()
    app.root.protocol('WM_DELETE_WINDOW', app.close)
    app.root.mainloop()
