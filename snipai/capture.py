"""Screenshot the monitor under the cursor, or a chosen region."""

from __future__ import annotations

import io
import logging
import sys
from dataclasses import dataclass
from typing import Callable

from PIL import Image

from snipai import SnipError

log = logging.getLogger("snipai")

MouseLocator = Callable[[], tuple[int, int]]


@dataclass(frozen=True)
class Monitor:
    index: int
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def as_mss(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }


def _mouse_position() -> tuple[int, int]:
    from pynput.mouse import Controller

    pos = Controller().position
    return int(pos[0]), int(pos[1])


def _monitors_from_sct(sct) -> list[Monitor]:
    monitors = []
    # monitors[0] is the virtual desktop; [1:] are physical screens.
    for index, raw in enumerate(sct.monitors[1:], start=1):
        monitors.append(
            Monitor(
                index=index,
                left=int(raw["left"]),
                top=int(raw["top"]),
                width=int(raw["width"]),
                height=int(raw["height"]),
            )
        )
    return monitors


def _pillow_grab(bbox: tuple[int, int, int, int] | None = None) -> Image.Image:
    from PIL import ImageGrab

    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["all_screens"] = True
    if bbox is not None:
        kwargs["bbox"] = bbox
    image = ImageGrab.grab(**kwargs)
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    return image


def list_monitors(sct=None) -> list[Monitor]:
    close = False
    if sct is None:
        try:
            import mss

            sct = mss.MSS()
            close = True
        except Exception as exc:
            log.debug("mss unavailable (%s); treating the desktop as one screen", exc)
            image = _pillow_grab()
            return [Monitor(1, 0, 0, image.width, image.height)]
    try:
        monitors = _monitors_from_sct(sct)
        if monitors:
            return monitors
        raise SnipError("No monitors found.")
    except SnipError:
        raise
    except Exception as exc:
        log.debug("mss monitor list failed (%s); falling back to Pillow", exc)
        image = _pillow_grab()
        return [Monitor(1, 0, 0, image.width, image.height)]
    finally:
        if close:
            sct.close()


def monitor_containing(x: int, y: int, monitors: list[Monitor] | None = None) -> Monitor:
    found = monitors if monitors is not None else list_monitors()
    if not found:
        raise SnipError("No monitors found.")
    for monitor in found:
        if monitor.contains(x, y):
            return monitor
    return found[0]


def current_monitor(mouse: MouseLocator | None = None) -> Monitor:
    locator = mouse or _mouse_position
    x, y = locator()
    return monitor_containing(x, y)


def _snapshot_mss(mouse: MouseLocator | None = None) -> tuple[Monitor, Image.Image]:
    import mss

    with mss.MSS() as sct:
        monitors = _monitors_from_sct(sct)
        if not monitors:
            raise SnipError("No monitors found.")
        locator = mouse or _mouse_position
        x, y = locator()
        monitor = monitor_containing(x, y, monitors)
        raw = sct.grab(monitor.as_mss())
        image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return monitor, image


def _snapshot_pillow() -> tuple[Monitor, Image.Image]:
    image = _pillow_grab()
    return Monitor(1, 0, 0, image.width, image.height), image


def snapshot_current(mouse: MouseLocator | None = None) -> tuple[Monitor, Image.Image]:
    """Grab the monitor under the cursor, or the whole desktop if mss cannot."""
    prefer_mss = sys.platform in {"win32", "darwin"}
    first, second = (
        (_snapshot_mss, _snapshot_pillow) if prefer_mss else (_snapshot_pillow, _snapshot_mss)
    )
    try:
        if first is _snapshot_mss:
            return first(mouse)
        return first()
    except SnipError:
        raise
    except Exception as exc:
        log.debug("primary snapshot failed (%s); trying fallback", exc)
        try:
            if second is _snapshot_mss:
                return second(mouse)
            return second()
        except SnipError:
            raise
        except Exception as exc2:
            raise SnipError(f"Could not capture the screen: {exc2}") from exc2


def grab_monitor(monitor: Monitor | None = None) -> Image.Image:
    target = monitor
    try:
        import mss

        if target is None:
            target = current_monitor()
        with mss.MSS() as sct:
            raw = sct.grab(target.as_mss())
            return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    except Exception as exc:
        log.debug("mss grab failed (%s); using Pillow ImageGrab", exc)
        if target is None:
            return _pillow_grab()
        return _pillow_grab(bbox=(target.left, target.top, target.right, target.bottom))


def grab_region(left: int, top: int, width: int, height: int) -> Image.Image:
    if width < 2 or height < 2:
        raise SnipError("Selection is too small.")
    try:
        import mss

        with mss.MSS() as sct:
            raw = sct.grab({"left": left, "top": top, "width": width, "height": height})
            return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    except Exception as exc:
        log.debug("mss region grab failed (%s); using Pillow ImageGrab", exc)
        return _pillow_grab(bbox=(left, top, left + width, top + height))


def prepare_png(image: Image.Image, max_width: int = 1600) -> bytes:
    work = image
    if work.mode not in {"RGB", "L"}:
        work = work.convert("RGB")
    if max_width > 0 and work.width > max_width:
        ratio = max_width / work.width
        work = work.resize(
            (max_width, max(1, int(work.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    buf = io.BytesIO()
    work.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def image_from_png(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png)).convert("RGB")
