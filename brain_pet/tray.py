"""System tray icon via pystray (optional – degrades gracefully if not installed)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .ui import BrainPetApp

try:
    import pystray
    from PIL import Image as _PILImage, ImageDraw as _ImageDraw
    _TRAY_OK = True
except ImportError:
    _TRAY_OK = False


def _icon_image(hex_color: str = '#3498DB', size: int = 64) -> '_PILImage.Image':
    img = _PILImage.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = _ImageDraw.Draw(img)
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    draw.ellipse([4, 4, size - 4, size - 4], fill=(r, g, b, 255))
    return img


class TrayIcon:
    def __init__(self, app: 'BrainPetApp') -> None:
        self._app = app
        self._icon: Optional['pystray.Icon'] = None
        self._ok = _TRAY_OK

    def start(self) -> None:
        if not self._ok:
            return
        try:
            menu = pystray.Menu(
                pystray.MenuItem('Show / Hide', self._on_show_hide),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('\U0001f3c3 Going to exercise',  lambda i, it: self._manual('EXERCISE')),
                pystray.MenuItem('\U0001f35c Going to eat',       lambda i, it: self._manual('EATING')),
                pystray.MenuItem('\U0001f634 Going to sleep',     lambda i, it: self._manual('SLEEPING')),
                pystray.MenuItem('\U0001f6b6 Going for a walk',   lambda i, it: self._manual('WALKING')),
                pystray.MenuItem('\U0001f4a1 Creative mode',      lambda i, it: self._manual('CREATIVE')),
                pystray.MenuItem('↩ Back at desk',           lambda i, it: self._manual(None)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('❌ Quit', self._on_quit),
            )
            self._icon = pystray.Icon(
                'Brain Pet',
                _icon_image(),
                'Brain Pet',
                menu,
            )
            self._icon.run_detached()
        except Exception as exc:
            print(f'[tray] Could not start: {exc}')
            self._ok = False

    def update(self, hex_color: str, state_name: str) -> None:
        if self._icon is None:
            return
        try:
            self._icon.icon = _icon_image(hex_color)
            self._icon.title = f'Brain Pet – {state_name}'
        except Exception:
            pass

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Callbacks (called from pystray thread → schedule on main thread)
    # ------------------------------------------------------------------

    def _on_show_hide(self, icon=None, item=None) -> None:
        app = self._app
        def _toggle():
            if app.root.state() == 'withdrawn':
                app.root.deiconify()
            else:
                app.root.withdraw()
        app.root.after(0, _toggle)

    def _on_quit(self, icon=None, item=None) -> None:
        self._app.root.after(0, self._app.close)

    def _manual(self, state_id: Optional[str]) -> None:
        self._app.root.after(0, lambda: self._app.set_manual_state(state_id))
