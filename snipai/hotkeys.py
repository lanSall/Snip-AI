"""Parse hotkey strings and listen globally (keyboard and extra mouse buttons)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

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
    "period": "period",
    "dot": "period",
    ".": "period",
    "comma": "comma",
    ",": "comma",
    "slash": "slash",
    "/": "slash",
    "backslash": "backslash",
    "\\": "backslash",
}

_Pynput_KEY = {
    "period": ".",
    "comma": ",",
    "slash": "/",
    "backslash": "\\",
}

_MOUSE_ALIASES = {
    "middle": "mouse_middle",
    "mouse_middle": "mouse_middle",
    "middleclick": "mouse_middle",
    "mouse_middle_click": "mouse_middle",
    "mouse4": "mouse4",
    "x1": "mouse4",
    "mouse_x1": "mouse4",
    "button8": "mouse4",
    "back": "mouse4",
    "mouse5": "mouse5",
    "x2": "mouse5",
    "mouse_x2": "mouse5",
    "button9": "mouse5",
    "forward": "mouse5",
    "mouse_left": "mouse_left",
    "mouse_right": "mouse_right",
}

_NEED_MODIFIER = frozenset(
    {
        "space",
        "enter",
        "tab",
        "mouse_right",
    }
)

_MOD_ORDER = ("ctrl", "alt", "shift", "cmd")


@dataclass(frozen=True)
class Binding:
    modifiers: tuple[str, ...]
    key: str

    @property
    def is_mouse(self) -> bool:
        return self.key.startswith("mouse")

    def canonical(self) -> str:
        return "+".join((*self.modifiers, self.key))


def parse_binding(hotkey: str) -> Binding:
    raw = (hotkey or "").strip().lower()
    if not raw:
        raise SnipError("Shortcut is empty.")
    parts = [part.strip() for part in raw.replace("-", "+").split("+") if part.strip()]
    if not parts:
        raise SnipError(f"Could not parse shortcut: {hotkey!r}")
    mods: list[str] = []
    key = ""
    for part in parts:
        if part in _MODIFIERS:
            name = _MODIFIERS[part]
            if name not in mods:
                mods.append(name)
            continue
        if part in _MOUSE_ALIASES:
            key = _MOUSE_ALIASES[part]
            continue
        if part.startswith("mouse") and part[5:].isdigit():
            key = part
            continue
        key = _KEY_ALIASES.get(part, part)
    if not key:
        raise SnipError("Press a key or mouse button, not only Ctrl/Alt/Shift.")
    mods_sorted = tuple(m for m in _MOD_ORDER if m in mods)
    return Binding(mods_sorted, key)


def normalize_binding(hotkey: str) -> str:
    return parse_binding(hotkey).canonical()


def format_binding(hotkey: str) -> str:
    """Human label: ``ctrl+shift+space`` → ``Ctrl+Shift+Space``."""
    try:
        binding = parse_binding(hotkey)
    except SnipError:
        return (hotkey or "").strip() or "None"
    labels = {
        "ctrl": "Ctrl",
        "alt": "Alt",
        "shift": "Shift",
        "cmd": "Win",
        "space": "Space",
        "period": ".",
        "slash": "/",
        "comma": ",",
        "backslash": "\\",
        "enter": "Enter",
        "tab": "Tab",
        "esc": "Esc",
        "mouse_middle": "Middle click",
        "mouse4": "Mouse 4 (side)",
        "mouse5": "Mouse 5 (side)",
        "mouse_left": "Left click",
        "mouse_right": "Right click",
    }
    key = labels.get(binding.key)
    if key is None:
        if binding.key.startswith("f") and binding.key[1:].isdigit():
            key = binding.key.upper()
        elif binding.key.startswith("mouse") and binding.key[5:].isdigit():
            key = f"Mouse {binding.key[5:]}"
        elif len(binding.key) == 1:
            key = binding.key.upper()
        else:
            key = binding.key
    bits = [labels.get(m, m.title()) for m in binding.modifiers]
    bits.append(key)
    return "+".join(bits)


def validate_binding(hotkey: str) -> str | None:
    """Return an error message if this shortcut is unsafe, else None."""
    try:
        binding = parse_binding(hotkey)
    except SnipError as exc:
        return str(exc)
    if binding.key == "mouse_left":
        return "Left click cannot be a shortcut — it would fire all the time."
    if binding.key == "mouse_right" and not binding.modifiers:
        return "Right click needs Ctrl, Alt, or Shift so normal clicking still works."
    if binding.key == "esc":
        return "Esc is used to cancel. Pick another key."
    if not binding.modifiers:
        if len(binding.key) == 1 and binding.key.isalnum():
            return "Add Ctrl, Alt, or Shift so typing still works."
        if binding.key in _NEED_MODIFIER:
            return f"Add Ctrl, Alt, or Shift to {format_binding(binding.key)}."
    return None


def to_pynput(hotkey: str) -> str:
    """Convert ``ctrl+shift+space`` into pynput's ``<ctrl>+<shift>+<space>``."""
    binding = parse_binding(hotkey)
    if binding.is_mouse:
        raise SnipError(f"Mouse shortcut {hotkey!r} is not a keyboard combo.")
    parsed: list[str] = []
    for mod in binding.modifiers:
        parsed.append(f"<{mod}>")
    key = _Pynput_KEY.get(binding.key, binding.key)
    if len(key) == 1:
        parsed.append(key)
    else:
        parsed.append(f"<{key}>")
    return "+".join(parsed)


def start_hotkeys(bindings: dict[str, Callable[[], None]]):
    """Start keyboard and/or mouse listeners. Caller must ``stop()`` later."""
    from pynput import keyboard, mouse

    kb_map: dict[str, Callable[[], None]] = {}
    mouse_map: dict[tuple[tuple[str, ...], str], Callable[[], None]] = {}
    for hotkey, callback in bindings.items():
        if not (hotkey or "").strip():
            continue
        binding = parse_binding(hotkey)
        err = validate_binding(binding.canonical())
        if err:
            log.warning("Skipping shortcut %s: %s", hotkey, err)
            continue
        guarded = _guard(binding.canonical(), callback)
        if binding.is_mouse:
            mouse_map[(binding.modifiers, binding.key)] = guarded
        else:
            kb_map[to_pynput(binding.canonical())] = guarded
    if not kb_map and not mouse_map:
        raise SnipError("No hotkeys configured.")

    parts: list = []
    mods = _ModifierTracker()
    if kb_map:
        listener = keyboard.GlobalHotKeys(kb_map)
        listener.start()
        parts.append(listener)
    if mouse_map:
        mod_listener = keyboard.Listener(on_press=mods.press, on_release=mods.release)
        mod_listener.start()
        parts.append(mod_listener)

        def on_click(_x, _y, button, pressed) -> None:
            if not pressed:
                return
            name = canonical_from_button(button)
            if not name:
                return
            cb = mouse_map.get((mods.snapshot(), name))
            if cb is not None:
                cb()

        m_listener = mouse.Listener(on_click=on_click)
        m_listener.start()
        parts.append(m_listener)

    log.info("Listening for %s", ", ".join(bindings))
    return _ListenerGroup(parts)


def canonical_from_button(button: object) -> str | None:
    name = getattr(button, "name", "") or ""
    if name in {"left", "right"}:
        return f"mouse_{name}"
    if name == "middle":
        return "mouse_middle"
    if name in {"x1", "button8"}:
        return "mouse4"
    if name in {"x2", "button9"}:
        return "mouse5"
    if name.startswith("button") and name[6:].isdigit():
        n = int(name[6:])
        if n >= 8:
            return f"mouse{n - 4}"
    if name.startswith("scroll"):
        return None
    return None


def start_shortcut_capture(
    on_capture: Callable[[str | None], None],
    *,
    ignore_ms: int = 280,
) -> Callable[[], None]:
    """Listen for the next keyboard combo or extra mouse button.

    ``on_capture`` gets a canonical shortcut string, or ``None`` if cancelled
    with Esc. Runs on the pynput thread — schedule Tk work from there.
    Returns ``stop``.
    """
    from pynput import keyboard, mouse

    state = {"done": False, "started": time.monotonic()}
    mods = _ModifierTracker()
    parts: list = []

    def finish(value: str | None) -> None:
        if state["done"]:
            return
        state["done"] = True
        for listener in parts:
            try:
                listener.stop()
            except Exception:
                pass
        try:
            on_capture(value)
        except Exception:
            log.exception("Shortcut capture callback failed")

    def too_soon() -> bool:
        return (time.monotonic() - state["started"]) * 1000 < ignore_ms

    def on_press(key) -> None:
        if state["done"] or too_soon():
            mods.press(key)
            return
        mods.press(key)
        if _is_escape(key):
            finish(None)
            return
        part = _key_to_part(key)
        if part is None:
            return
        combo = Binding(mods.snapshot(), part).canonical()
        err = validate_binding(combo)
        if err:
            log.info("Ignored shortcut %s (%s)", combo, err)
            return
        finish(combo)

    def on_release(key) -> None:
        mods.release(key)

    def on_click(_x, _y, button, pressed) -> None:
        if not pressed or state["done"] or too_soon():
            return
        name = canonical_from_button(button)
        if not name:
            return
        combo = Binding(mods.snapshot(), name).canonical()
        err = validate_binding(combo)
        if err:
            log.info("Ignored shortcut %s (%s)", combo, err)
            return
        finish(combo)

    kb = keyboard.Listener(on_press=on_press, on_release=on_release)
    ms = mouse.Listener(on_click=on_click)
    parts.extend((kb, ms))
    kb.start()
    ms.start()

    def stop() -> None:
        if state["done"]:
            return
        state["done"] = True
        for listener in parts:
            try:
                listener.stop()
            except Exception:
                pass

    return stop


def _is_escape(key: object) -> bool:
    name = getattr(key, "name", "") or ""
    return name in {"esc", "escape"}


def _key_to_part(key: object) -> str | None:
    name = (getattr(key, "name", None) or "").lower()
    if name in {
        "ctrl",
        "ctrl_l",
        "ctrl_r",
        "alt",
        "alt_l",
        "alt_r",
        "alt_gr",
        "shift",
        "shift_l",
        "shift_r",
        "cmd",
        "cmd_l",
        "cmd_r",
        "caps_lock",
        "num_lock",
    }:
        return None
    if name:
        name = name.removesuffix("_l").removesuffix("_r")
        if name in _MODIFIERS:
            return None
        if name == "esc":
            return None
        return _KEY_ALIASES.get(name, name)
    char = getattr(key, "char", None)
    if not char:
        return None
    if len(char) == 1 and ord(char) < 32:
        char = chr(ord(char) + 96)  # Ctrl+A → a
    if char.isprintable():
        return _KEY_ALIASES.get(char.lower(), char.lower())
    return None


class _ModifierTracker:
    def __init__(self) -> None:
        self._down: set[str] = set()
        self._lock = threading.Lock()

    def press(self, key: object) -> None:
        name = _modifier_name(key)
        if not name:
            return
        with self._lock:
            self._down.add(name)

    def release(self, key: object) -> None:
        name = _modifier_name(key)
        if not name:
            return
        with self._lock:
            self._down.discard(name)

    def snapshot(self) -> tuple[str, ...]:
        with self._lock:
            down = set(self._down)
        return tuple(m for m in _MOD_ORDER if m in down)


def _modifier_name(key: object) -> str | None:
    name = (getattr(key, "name", None) or "").lower()
    if name in {"ctrl", "ctrl_l", "ctrl_r", "control"}:
        return "ctrl"
    if name in {"alt", "alt_l", "alt_r", "alt_gr", "option"}:
        return "alt"
    if name in {"shift", "shift_l", "shift_r"}:
        return "shift"
    if name in {"cmd", "cmd_l", "cmd_r", "win", "super", "meta"}:
        return "cmd"
    return None


class _ListenerGroup:
    def __init__(self, parts: list) -> None:
        self._parts = parts

    def stop(self) -> None:
        for listener in self._parts:
            try:
                listener.stop()
            except Exception:
                log.debug("Hotkey listener stop failed", exc_info=True)
        self._parts = []


def _guard(hotkey: str, callback: Callable[[], None]) -> Callable[[], None]:
    def wrapped() -> None:
        try:
            callback()
        except Exception:
            log.exception("Hotkey %s handler failed", hotkey)

    return wrapped
