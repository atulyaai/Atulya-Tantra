"""System-tray icon for the always-listening app (Windows, macOS, Linux).

The dot shows what Atulya is doing — saffron: listening, turmeric: thinking,
green: speaking, grey: muted, red: needs sign-in — and the menu mutes the
microphone, opens the web UI or quits. Needs ``pystray`` and ``Pillow``.
"""
from __future__ import annotations

import threading
import webbrowser
from typing import Any, Callable

STATUS_COLOURS = {
    "listening": (255, 153, 51),   # saffron
    "thinking": (244, 196, 48),    # turmeric
    "speaking": (46, 184, 92),     # India green
    "muted": (120, 120, 130),
    "sign-in": (240, 90, 68),      # sindoor
}


def tray_available() -> bool:
    try:
        import PIL  # noqa: F401
        import pystray  # noqa: F401
    except Exception:  # noqa: BLE001 - also no display on a headless machine
        return False
    return True


def icon_image(status: str, size: int = 64) -> Any:
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, size - 2, size - 2), fill=(10, 13, 31, 255))
    colour = STATUS_COLOURS.get(status, STATUS_COLOURS["listening"])
    pad = size // 5
    draw.ellipse((pad, pad, size - pad, size - pad), fill=(*colour, 255))
    dot = size // 8
    c = size // 2
    draw.ellipse((c - dot, c - dot, c + dot, c + dot), fill=(251, 246, 238, 255))
    return img


class TrayApp:
    def __init__(self, engine: Any, url: str, on_quit: Callable[[], None]):
        self.engine = engine
        self.url = url
        self.on_quit = on_quit
        self.icon: Any = None
        self._lock = threading.Lock()

    def _status(self) -> str:
        if getattr(self.engine, "needs_sign_in", False):
            return "sign-in"
        return str(getattr(self.engine, "status", "listening"))

    def update(self, _status: str = "") -> None:
        with self._lock:
            if self.icon is not None:
                status = self._status()
                self.icon.icon = icon_image(status)
                self.icon.title = f"Atulya — {status}"

    def run(self) -> None:
        """Blocks: the tray owns the main thread (required on macOS)."""
        import pystray

        def toggle(_icon: Any, _item: Any) -> None:
            self.engine.toggle_mute()
            self.update()

        def quit_app(icon: Any, _item: Any) -> None:
            self.on_quit()
            icon.stop()

        menu = pystray.Menu(
            pystray.MenuItem(lambda _item: f"Atulya — {self._status()}", None, enabled=False),
            pystray.MenuItem(lambda _item: "Unmute microphone" if self.engine.muted else "Mute microphone", toggle),
            pystray.MenuItem("Open Atulya", lambda _i, _t: webbrowser.open(self.url)),
            pystray.MenuItem("Quit", quit_app),
        )
        self.icon = pystray.Icon("atulya", icon_image(self._status()), "Atulya — listening", menu)
        self.engine.on_status = self.update
        self.icon.run()
