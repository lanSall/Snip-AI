"""Parse hotkey strings and listen globally."""

from __future__ import annotations

import logging
from collections.abc import Callable

from snipai import SnipError

log = logging.getLogger("snipai")

_MODIFIERS = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "shift": "shift",
    "cmd": "cmd",
    "command": "cmd",
    "win": "cmd",
    "super": "cmd",
    "meta": "cmd",
}

_KEY_ALIASES = {
    "esc": "esc",
    "escape": "esc",
    "space": "space",
    "tab": "tab",
    "enter": "enter",
    "return": "enter",
    "period": ".",
    "dot": ".",
    "slash": "/",
    "backslash": "\\",
}


def to_pynput(hotkey: str) -> str:
    """Convert ``ctrl+shift+space`` into pynput's ``<ctrl>+<shift>+<space>``."""
    raw = (hotkey or "").strip().lower()
    if not raw:
        raise SnipError("Hotkey is empty.")
    parts = [part.strip() for part in raw.replace("-", "+").split("+") if part.strip()]
    if not parts:
        raise SnipError(f"Could not parse hotkey: {hotkey!r}")
    parsed: list[str] = []
    for part in parts:
        if part in _MODIFIERS:
            parsed.append(f"<{_MODIFIERS[part]}>")
            continue
        key = _KEY_ALIASES.get(part, part)
        if len(key) == 1:
            parsed.append(key)
        else:
            parsed.append(f"<{key}>")
    return "+".join(parsed)


def start_hotkeys(bindings: dict[str, Callable[[], None]]):
    """Start a pynput listener. Caller must ``stop()`` it later."""
    from pynput import keyboard

    mapping = {}
    for hotkey, callback in bindings.items():
        if not hotkey.strip():
            continue
        combo = to_pynput(hotkey)
        mapping[combo] = _guard(hotkey, callback)
    if not mapping:
        raise SnipError("No hotkeys configured.")
    listener = keyboard.GlobalHotKeys(mapping)
    listener.start()
    log.info("Listening for %s", ", ".join(mapping))
    return listener


def _guard(hotkey: str, callback: Callable[[], None]) -> Callable[[], None]:
    def wrapped() -> None:
        try:
            callback()
        except Exception:
            log.exception("Hotkey %s handler failed", hotkey)

    return wrapped
