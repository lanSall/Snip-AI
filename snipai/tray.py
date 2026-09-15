"""Windows (and optional Linux) tray icon: settings, open at login, quit."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from typing import Any

from PIL import Image, ImageDraw

log = logging.getLogger("snipai")


def tray_available() -> bool:
    if os.name != "nt" and not os.environ.get("SNIPAI_TRAY"):
        return False
    try:
        import pystray  # noqa: F401
    except Exception:
        return False
    return True


def make_icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (27, 29, 33, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((6, 6, 58, 58), radius=14, fill=(110, 231, 183, 255))
    draw.rectangle((20, 22, 44, 42), outline=(5, 46, 26, 255), width=4)
    draw.line((28, 18, 36, 18), fill=(5, 46, 26, 255), width=4)
    return img


def start_tray(
    *,
    on_settings: Callable[[], None],
    on_quit: Callable[[], None],
    on_history: Callable[[], None] | None = None,
    on_ask: Callable[[], None] | None = None,
) -> Any:
    """Run the tray icon in a background thread. Returns the icon (call ``stop()``)."""
    import pystray
    from pystray import Menu, MenuItem

    from snipai import autostart

    def ask(_icon: Any, _item: Any) -> None:
        log.info("Tray: Ask")
        try:
            if on_ask:
                on_ask()
        except Exception:
            log.exception("Tray Ask failed")

    def history(_icon: Any, _item: Any) -> None:
        log.info("Tray: Last answers")
        try:
            if on_history:
                on_history()
        except Exception:
            log.exception("Tray Last answers failed")

    def settings(_icon: Any, _item: Any) -> None:
        log.info("Tray: Settings")
        try:
            on_settings()
        except Exception:
            log.exception("Tray Settings failed")

    def quit_app(icon: Any, _item: Any) -> None:
        log.info("Tray: Quit")
        try:
            icon.stop()
        except Exception:
            pass
        try:
            on_quit()
        except Exception:
            log.exception("Tray Quit failed")

    def toggle_login(icon: Any, _item: Any) -> None:
        try:
            autostart.set_enabled(not autostart.is_enabled())
        except OSError as exc:
            log.warning("Could not change Open at login: %s", exc)
        try:
            icon.update_menu()
        except Exception:
            pass

    items = []
    if on_ask is not None:
        items.append(MenuItem("Ask a question", ask))
    if on_history is not None:
        items.append(MenuItem("Last answers", history))
    items.extend(
        [
            MenuItem("Settings (key and model)", settings, default=True),
            MenuItem("Open at login", toggle_login, checked=lambda item: autostart.is_enabled()),
            Menu.SEPARATOR,
            MenuItem("Quit snip-ai", quit_app),
        ]
    )
    menu = Menu(*items)
    icon = pystray.Icon("snip-ai", make_icon_image(), "snip-ai", menu)
    if hasattr(icon, "run_detached"):
        icon.run_detached()
    else:
        thread = threading.Thread(target=icon.run, name="snipai-tray", daemon=True)
        thread.start()
    return icon
