"""Orchestrate capture → solve → clipboard → toast."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from snipai import SnipError
from snipai.capture import prepare_png, snapshot_current
from snipai.clipboard import copy_text
from snipai.config import Config
from snipai.formatting import parse_solution, toast_body
from snipai.hotkeys import start_hotkeys
from snipai.solver import Solver
from snipai.ui import ToastUI, select_region

log = logging.getLogger("snipai")


class SnipApp:
    def __init__(self, config: Config, solver: Solver, ui: ToastUI) -> None:
        self.config = config
        self.solver = solver
        self.ui = ui
        self._lock = threading.Lock()
        self._busy = False

    def capture_screen(self) -> None:
        self._start_job("screen")

    def capture_region(self) -> None:
        self._start_job("region")

    def solve_png(self, png: bytes, *, notify: bool = True) -> str:
        answer = self.solver.solve(png)
        headline, full = parse_solution(answer)
        if self.config.clipboard:
            copy_text(full or answer)
        if notify:
            body = toast_body(answer, max_chars=self.config.notify.max_chars)
            self._toast("Answer", body)
        log.info("Answer: %s", headline)
        return answer

    def run_hotkeys(self) -> None:
        listener = start_hotkeys(
            {
                self.config.hotkey: self.capture_screen,
                self.config.region_hotkey: self.capture_region,
            }
        )
        self._toast(
            "snip-ai",
            f"{self.config.hotkey} screen · {self.config.region_hotkey} snip",
            duration_ms=3500,
        )
        try:
            self.ui.mainloop()
        finally:
            listener.stop()

    def _toast(self, title: str, body: str, duration_ms: int | None = None) -> None:
        # Bind values in default args so Python 3.13 cannot clear `exc` before the toast runs.
        self.ui.schedule(
            lambda t=title, b=body, d=duration_ms: self.ui.show_toast(t, b, duration_ms=d)
        )

    def _start_job(self, mode: str) -> None:
        with self._lock:
            if self._busy:
                self._toast("snip-ai", "Still solving…", duration_ms=2000)
                return
            self._busy = True
        thread = threading.Thread(target=self._job, args=(mode,), daemon=True)
        thread.start()

    def _job(self, mode: str) -> None:
        try:
            png = self._capture(mode)
            if png is None:
                return
            if self.config.save_shots:
                _save_shot(self.config.resolved_shots_dir(), png)
            self._toast("snip-ai", "Solving…", duration_ms=2500)
            self.solve_png(png, notify=True)
        except SnipError as exc:
            message = str(exc)
            log.warning("%s", message)
            self._toast("snip-ai", message, duration_ms=5000)
        except Exception:
            log.exception("Capture/solve failed")
            self._toast("snip-ai", "Something went wrong. See the log.", duration_ms=5000)
        finally:
            with self._lock:
                self._busy = False

    def _capture(self, mode: str) -> bytes | None:
        monitor, image = snapshot_current()
        if mode == "region":
            selected = {"image": None}
            done = threading.Event()

            def pick() -> None:
                try:
                    selected["image"] = select_region(self.ui, image, monitor.left, monitor.top)
                finally:
                    done.set()

            self.ui.schedule(pick)
            done.wait(timeout=120)
            cropped = selected["image"]
            if cropped is None:
                return None
            image = cropped
        return prepare_png(image, max_width=self.config.max_image_width)


def _save_shot(directory: Path, png: bytes) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = directory / f"snip-{stamp}.png"
    path.write_bytes(png)
    log.info("Saved screenshot to %s", path)
