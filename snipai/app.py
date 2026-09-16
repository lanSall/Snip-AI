"""Orchestrate capture → solve → clipboard → toast."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from typing import Any, Protocol

from snipai import SnipError
from snipai.capture import prepare_png, snapshot_current
from snipai.clipboard import copy_text
from snipai.config import Config, load_config
from snipai.formatting import parse_solution, toast_body
from snipai.history import AnswerHistory
from snipai.hotkeys import start_hotkeys
from snipai.solver import Solver, make_solver

log = logging.getLogger("snipai")


class UserInterface(Protocol):
    def schedule(self, fn: Any) -> None: ...

    def show_toast(
        self,
        title: str,
        body: str,
        *,
        duration_ms: int | None = None,
        on_click: Any = None,
        actions: Any = None,
    ) -> None: ...

    def mainloop(self) -> None: ...

    def destroy(self) -> None: ...


class SnipApp:
    def __init__(
        self,
        config: Config,
        solver: Solver,
        ui: UserInterface,
        *,
        config_path: Path | None = None,
        history: AnswerHistory | None = None,
    ) -> None:
        self.config = config
        self.solver = solver
        self.ui = ui
        self.config_path = config_path
        self.history = history or AnswerHistory()
        self._lock = threading.Lock()
        self._busy = False
        self._settings_open = False
        self._history_win = None
        self._ask_win = None
        self._listener = None
        self._hotkeys_running = False
        self._paused = False
        self._last_png: bytes | None = None
        self._last_answer = ""

    def capture_screen(self) -> None:
        self._start_job("screen")

    def capture_region(self) -> None:
        self._start_job("region")

    def solve_png(self, png: bytes, *, notify: bool = True) -> str:
        if png:
            self._last_png = png
        return self._deliver(self.solver.solve(png), notify=notify, snip=True)

    def solve_question(self, question: str, *, notify: bool = True) -> str:
        return self._deliver(self.solver.ask(question), notify=notify)

    def solve_follow_up(self, question: str, *, notify: bool = True) -> str:
        if not self._last_png:
            raise SnipError("Snip something first.")
        return self._deliver(
            self.solver.follow_up(self._last_png, self._last_answer, question),
            notify=notify,
            snip=True,
        )

    def retry_last(self) -> None:
        if not self._last_png:
            self._toast("snip-ai", "Snip something first.", duration_ms=2500)
            return
        self._start_retry_job()

    def open_follow_up(self) -> None:
        if not self._last_png:
            self._toast("snip-ai", "Snip something first.", duration_ms=2500)
            return
        log.info("Follow-up requested")
        self.ui.schedule(lambda: self._open_ask_ui(follow_up=True))

    def toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._hotkeys_running:
            self._start_hotkey_listener()
        if self._paused:
            self._toast("snip-ai", "Shortcuts paused", duration_ms=2500)
        else:
            self._toast("snip-ai", "Shortcuts on", duration_ms=2500)

    def is_paused(self) -> bool:
        return self._paused

    def _deliver(self, answer: str, *, notify: bool, snip: bool = False) -> str:
        headline, full = parse_solution(answer)
        text = full or answer
        self._last_answer = text
        entry = self.history.add(headline, text)
        if self.config.clipboard:
            copy_text(text)
        if notify:
            body = toast_body(answer, max_chars=self.config.notify.max_chars)
            actions = None
            if snip:
                actions = [
                    ("Retry", self.retry_last),
                    ("Follow up", self.open_follow_up),
                ]
            self._toast(
                "Answer",
                body,
                on_click=lambda e=entry: self.open_history(e.id),
                actions=actions,
            )
        log.info("Answer: %s", headline)
        return answer

    def open_history(self, select_id: str | None = None) -> None:
        self.ui.schedule(lambda: self._open_history_ui(select_id))

    def _open_history_ui(self, select_id: str | None = None) -> None:
        from snipai.history_ui import show_history_window

        root = getattr(self.ui, "root", None)
        if root is None:
            return
        try:
            self._history_win = show_history_window(
                self.history,
                master=root,
                select_id=select_id,
                window=self._history_win,
            )
        except Exception as exc:
            log.exception("History window failed")
            self._toast("snip-ai", f"Could not open answers: {exc}", duration_ms=4000)

    def open_ask(self) -> None:
        """Hotkey and tray: small toast-like window to type a question."""
        log.info("Ask requested")
        self.ui.schedule(lambda: self._open_ask_ui(follow_up=False))

    def _open_ask_ui(self, follow_up: bool = False) -> None:
        from snipai.ui import show_ask_window

        root = getattr(self.ui, "root", None)
        if root is None:
            return
        try:
            self._ask_win = show_ask_window(
                self.ui,
                on_submit=self._on_ask_submit,
                window=self._ask_win,
                follow_up=follow_up,
                has_last_snip=bool(self._last_png),
            )
        except Exception as exc:
            log.exception("Ask window failed")
            self._toast("snip-ai", f"Could not open Ask: {exc}", duration_ms=4000)

    def _on_ask_submit(self, question: str, *, use_last_snip: bool = False) -> None:
        self._ask_win = None
        if use_last_snip:
            self._start_follow_up_job(question)
        else:
            self._start_ask_job(question)

    def open_settings(self) -> None:
        """Hotkey and tray both land here; the dialog must run on the Tk thread."""
        log.info("Settings requested")
        self.ui.schedule(self._open_settings_ui)

    def _open_settings_ui(self) -> None:
        from snipai.config import save_config
        from snipai.setup_ui import run_setup_wizard

        if self.config_path is None:
            self._toast("snip-ai", "No settings file to edit.", duration_ms=3000)
            return
        if self._lift_open_settings():
            return
        self._settings_open = True
        self._stop_hotkeys()
        try:
            root = getattr(self.ui, "root", None)
            updated = run_setup_wizard(self.config, master=root, running=True)
            if updated is not None:
                save_config(updated, self.config_path)
                self.config = load_config(self.config_path)
                self.solver = make_solver(self.config)
                if hasattr(self.ui, "notify"):
                    self.ui.notify = self.config.notify
                self._toast("snip-ai", f"Using {self.config.model}", duration_ms=2500)
        except Exception as exc:
            log.exception("Settings failed")
            self._toast("snip-ai", f"Settings failed: {exc}", duration_ms=4000)
        finally:
            self._settings_open = False
            if self._hotkeys_running:
                self._start_hotkey_listener()

    def _lift_open_settings(self) -> bool:
        if not self._settings_open:
            return False
        root = getattr(self.ui, "root", None)
        if root is None:
            return True
        try:
            import tkinter as tk

            for child in root.winfo_children():
                try:
                    if str(child.wm_title()) == "snip-ai settings":
                        child.deiconify()
                        child.lift()
                        child.focus_force()
                        return True
                except tk.TclError:
                    continue
        except Exception:
            log.debug("Could not raise existing settings window", exc_info=True)
        return True

    def run_hotkeys(self) -> None:
        self._hotkeys_running = True
        self._start_hotkey_listener()
        from snipai.hotkeys import format_binding

        bits = [
            f"{format_binding(self.config.hotkey)} screen",
            f"{format_binding(self.config.region_hotkey)} snip",
        ]
        if self.config.ask_hotkey:
            bits.append(f"{format_binding(self.config.ask_hotkey)} ask")
        if self.config.settings_hotkey:
            bits.append(f"{format_binding(self.config.settings_hotkey)} settings")
        self._toast("snip-ai", " · ".join(bits), duration_ms=4000)
        try:
            self.ui.mainloop()
        finally:
            self._hotkeys_running = False
            self._stop_hotkeys()

    def _bindings(self) -> dict:
        if self._paused:
            if self.config.settings_hotkey:
                return {self.config.settings_hotkey: self.open_settings}
            return {}
        bindings = {
            self.config.hotkey: self.capture_screen,
            self.config.region_hotkey: self.capture_region,
        }
        if self.config.ask_hotkey:
            bindings[self.config.ask_hotkey] = self.open_ask
        if self.config.settings_hotkey:
            bindings[self.config.settings_hotkey] = self.open_settings
        return bindings

    def _start_hotkey_listener(self) -> None:
        self._stop_hotkeys()
        bindings = self._bindings()
        if not bindings:
            return
        try:
            self._listener = start_hotkeys(bindings)
        except SnipError as exc:
            log.warning("Could not start shortcuts: %s", exc)
            self._toast("snip-ai", str(exc), duration_ms=4000)
            self._listener = None

    def _stop_hotkeys(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is None:
            return
        try:
            listener.stop()
        except Exception:
            log.debug("Hotkey listener stop failed", exc_info=True)

    def _toast(
        self,
        title: str,
        body: str,
        duration_ms: int | None = None,
        on_click: Any = None,
        actions: Any = None,
    ) -> None:
        # Bind values in default args so Python 3.13 cannot clear `exc` before the toast runs.
        self.ui.schedule(
            lambda t=title, b=body, d=duration_ms, c=on_click, a=actions: self.ui.show_toast(
                t, b, duration_ms=d, on_click=c, actions=a
            )
        )

    def _start_job(self, mode: str) -> None:
        with self._lock:
            if self._busy:
                self._toast("snip-ai", "Still solving…", duration_ms=2000)
                return
            self._busy = True
        thread = threading.Thread(target=self._job, args=(mode,), daemon=True)
        thread.start()

    def _start_ask_job(self, question: str) -> None:
        with self._lock:
            if self._busy:
                self._toast("snip-ai", "Still solving…", duration_ms=2000)
                return
            self._busy = True
        thread = threading.Thread(target=self._ask_job, args=(question,), daemon=True)
        thread.start()

    def _start_follow_up_job(self, question: str) -> None:
        with self._lock:
            if self._busy:
                self._toast("snip-ai", "Still solving…", duration_ms=2000)
                return
            self._busy = True
        thread = threading.Thread(target=self._follow_up_job, args=(question,), daemon=True)
        thread.start()

    def _start_retry_job(self) -> None:
        with self._lock:
            if self._busy:
                self._toast("snip-ai", "Still solving…", duration_ms=2000)
                return
            self._busy = True
        thread = threading.Thread(target=self._retry_job, daemon=True)
        thread.start()

    def _follow_up_job(self, question: str) -> None:
        try:
            self._toast("snip-ai", "Solving…", duration_ms=2500)
            self.solve_follow_up(question, notify=True)
        except SnipError as exc:
            message = str(exc)
            log.warning("%s", message)
            self._toast("snip-ai", message, duration_ms=5000)
        except Exception:
            log.exception("Follow-up failed")
            self._toast("snip-ai", "Something went wrong. See the log.", duration_ms=5000)
        finally:
            with self._lock:
                self._busy = False

    def _retry_job(self) -> None:
        try:
            png = self._last_png
            if not png:
                self._toast("snip-ai", "Snip something first.", duration_ms=2500)
                return
            self._toast("snip-ai", "Retrying…", duration_ms=2500)
            self.solve_png(png, notify=True)
        except SnipError as exc:
            message = str(exc)
            log.warning("%s", message)
            self._toast("snip-ai", message, duration_ms=5000)
        except Exception:
            log.exception("Retry failed")
            self._toast("snip-ai", "Something went wrong. See the log.", duration_ms=5000)
        finally:
            with self._lock:
                self._busy = False

    def _ask_job(self, question: str) -> None:
        try:
            self._toast("snip-ai", "Solving…", duration_ms=2500)
            self.solve_question(question, notify=True)
        except SnipError as exc:
            message = str(exc)
            log.warning("%s", message)
            self._toast("snip-ai", message, duration_ms=5000)
        except Exception:
            log.exception("Ask/solve failed")
            self._toast("snip-ai", "Something went wrong. See the log.", duration_ms=5000)
        finally:
            with self._lock:
                self._busy = False

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
                from snipai.ui import select_region

                try:
                    selected["image"] = select_region(self.ui, image, monitor.left, monitor.top)
                finally:
                    done.set()

            self.ui.schedule(pick)
            finished = done.wait(timeout=120)
            if not finished:
                cancel = getattr(self.ui, "cancel_snip", None)
                if callable(cancel):
                    self.ui.schedule(cancel)
                done.wait(timeout=5)
                log.warning("Region snip timed out")
                return None
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
