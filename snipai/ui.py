"""Discreet, no-focus toasts in a screen corner."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from collections.abc import Callable
from queue import Empty, SimpleQueue
from typing import Any

from snipai.config import NotifyConfig

log = logging.getLogger("snipai")

BG = "#1b1d21"
FG = "#f3f4f6"
MUTED = "#9aa3af"
ACCENT = "#6ee7b7"
BORDER = "#2e323a"
PAD = 16
TOAST_WIDTH = 320

_POSITIONS = {
    "bottom-right": ("e", "s"),
    "bottom-left": ("w", "s"),
    "top-right": ("e", "n"),
    "top-left": ("w", "n"),
}


class ToastUI:
    """Owns a hidden Tk root so toasts and the snip overlay can share a loop."""

    def __init__(self, notify: NotifyConfig | None = None) -> None:
        self.notify = notify or NotifyConfig()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("snip-ai")
        self._toast: tk.Toplevel | None = None
        self._after_id: str | None = None
        # Tray and hotkey threads must not call Tk directly (especially on Windows).
        self._jobs: SimpleQueue[Callable[[], None]] = SimpleQueue()
        self._snip_overlay: tk.Toplevel | None = None
        self.root.after(25, self._pump_jobs)

    def schedule(self, fn: Callable[[], None]) -> None:
        self._jobs.put(fn)

    def _pump_jobs(self) -> None:
        try:
            self.root.after(25, self._pump_jobs)
        except tk.TclError:
            return
        # Run jobs idle so wait_window (snip overlay / settings) is not nested
        # inside this repeating timer.
        while True:
            try:
                fn = self._jobs.get_nowait()
            except Empty:
                break

            def _run(job: Callable[[], None] = fn) -> None:
                try:
                    job()
                except Exception:
                    log.exception("UI callback failed")

            try:
                self.root.after_idle(_run)
            except tk.TclError:
                break

    def cancel_snip(self) -> None:
        """Close a stuck region-snip overlay (timeout or a second cancel)."""
        top = getattr(self, "_snip_overlay", None)
        if top is None:
            return
        try:
            top.destroy()
        except tk.TclError:
            pass
        self._snip_overlay = None

    def mainloop(self) -> None:
        self.root.mainloop()

    def quit(self) -> None:
        self.schedule(self.root.quit)

    def destroy(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def show_toast(
        self,
        title: str,
        body: str,
        *,
        duration_ms: int | None = None,
        on_click: Callable[[], None] | None = None,
    ) -> None:
        if not self.notify.enabled:
            log.info("%s: %s", title, body)
            return
        duration = self.notify.duration_ms if duration_ms is None else duration_ms
        self._close_toast()
        win = tk.Toplevel(self.root)
        self._toast = win
        win.withdraw()
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            win.attributes("-type", "notification")
        except tk.TclError:
            pass
        try:
            win.attributes("-alpha", 0.96)
        except tk.TclError:
            pass

        frame = tk.Frame(win, bg=BORDER, padx=1, pady=1)
        frame.pack(fill="both", expand=True)
        inner = tk.Frame(frame, bg=BG, padx=12, pady=10)
        inner.pack(fill="both", expand=True)

        tk.Label(
            inner,
            text=title,
            bg=BG,
            fg=ACCENT,
            font=("Segoe UI", 9, "bold") if sys.platform == "win32" else ("sans-serif", 9, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            inner,
            text=body,
            bg=BG,
            fg=FG,
            font=("Segoe UI", 10) if sys.platform == "win32" else ("sans-serif", 10),
            wraplength=TOAST_WIDTH - 24,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(4, 0))
        hint = "Copied · click for full answer" if on_click else "click to dismiss"
        tk.Label(
            inner,
            text=hint,
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 8) if sys.platform == "win32" else ("sans-serif", 8),
            anchor="w",
        ).pack(fill="x", pady=(6, 0))

        def handle(_event: object | None = None) -> None:
            self._close_toast()
            if on_click is not None:
                try:
                    on_click()
                except Exception:
                    log.exception("Toast click failed")

        def bind_click(widget: tk.Misc) -> None:
            widget.bind("<Button-1>", handle)
            for child in widget.winfo_children():
                bind_click(child)

        bind_click(win)

        win.update_idletasks()
        self._place(win)
        _make_no_activate(win)
        win.deiconify()
        win.lift()
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        if duration > 0:
            self._after_id = self.root.after(duration, self._close_toast)

    def _place(self, win: tk.Toplevel) -> None:
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        win.update_idletasks()
        width = max(win.winfo_reqwidth(), TOAST_WIDTH)
        height = win.winfo_reqheight()
        x_anchor, y_anchor = _POSITIONS.get(self.notify.position, _POSITIONS["bottom-right"])
        x = PAD if x_anchor == "w" else screen_w - width - PAD
        y = PAD if y_anchor == "n" else screen_h - height - PAD
        win.geometry(f"{width}x{height}+{x}+{y}")

    def _close_toast(self) -> None:
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if self._toast is not None:
            try:
                self._toast.destroy()
            except tk.TclError:
                pass
            self._toast = None


def _make_no_activate(win: tk.Toplevel) -> None:
    """Keep the toast from stealing keyboard focus (especially on Windows)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        GWL_EXSTYLE = -20
        WS_EX_NOACTIVATE = 0x08000000
        WS_EX_TOOLWINDOW = 0x00000080
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        if not hwnd:
            hwnd = win.winfo_id()
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        )
    except Exception as exc:
        log.debug("Could not set WS_EX_NOACTIVATE: %s", exc)


def configure_dpi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _force_activate(win: tk.Misc) -> None:
    """Give keyboard focus to an overrideredirect window (Windows otherwise ignores Esc)."""
    try:
        win.lift()
        win.focus_force()
    except tk.TclError:
        pass
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(win.winfo_id())
        user32 = ctypes.windll.user32
        parent = user32.GetParent(hwnd)
        if parent:
            hwnd = parent
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    except Exception as exc:
        log.debug("Could not focus snip overlay: %s", exc)


def select_region(ui: ToastUI, image: Any, monitor_left: int, monitor_top: int):
    """Interactive rectangle snip. Returns a cropped PIL image or None."""
    from PIL import ImageTk

    result: dict[str, Any] = {"image": None}
    closed = {"done": False}
    top = tk.Toplevel(ui.root)
    ui._snip_overlay = top
    top.overrideredirect(True)
    try:
        top.attributes("-topmost", True)
    except tk.TclError:
        pass
    width, height = image.size
    top.geometry(f"{width}x{height}+{monitor_left}+{monitor_top}")

    canvas = tk.Canvas(top, width=width, height=height, highlightthickness=0, cursor="crosshair")
    canvas.pack(fill="both", expand=True)
    photo = ImageTk.PhotoImage(image)
    canvas.create_image(0, 0, anchor="nw", image=photo)
    canvas.image = photo  # prevent GC

    rect_id = canvas.create_rectangle(0, 0, 0, 0, outline=ACCENT, width=2)
    start = {"x": 0, "y": 0, "dragging": False}

    def finish(crop: Any) -> None:
        if closed["done"]:
            return
        closed["done"] = True
        result["image"] = crop
        ui._snip_overlay = None
        try:
            ui.root.unbind_all("<Escape>")
        except tk.TclError:
            pass
        try:
            top.grab_release()
        except tk.TclError:
            pass
        try:
            top.destroy()
        except tk.TclError:
            pass

    def on_press(event: tk.Event) -> None:
        start["x"] = event.x
        start["y"] = event.y
        start["dragging"] = True
        canvas.coords(rect_id, event.x, event.y, event.x, event.y)

    def on_move(event: tk.Event) -> None:
        if not start["dragging"]:
            return
        canvas.coords(rect_id, start["x"], start["y"], event.x, event.y)

    def on_release(event: tk.Event) -> None:
        if not start["dragging"]:
            return
        start["dragging"] = False
        x0, x1 = sorted((start["x"], event.x))
        y0, y1 = sorted((start["y"], event.y))
        if x1 - x0 < 8 or y1 - y0 < 8:
            finish(None)
            return
        finish(image.crop((x0, y0, x1, y1)))

    def on_escape(_event: tk.Event | None = None) -> str:
        finish(None)
        return "break"

    font = ("Segoe UI", 11) if sys.platform == "win32" else ("sans-serif", 11)
    bar = tk.Frame(top, bg=BG, padx=14, pady=8)
    bar.place(relx=0.5, y=16, anchor="n")
    tk.Label(bar, text="Drag a rectangle", bg=BG, fg=FG, font=font).pack(side="left", padx=(0, 12))
    tk.Button(
        bar,
        text="Cancel",
        command=lambda: finish(None),
        bg=BORDER,
        fg=FG,
        activebackground="#3a404a",
        activeforeground=FG,
        highlightthickness=0,
        bd=0,
        relief="flat",
        font=font,
        padx=12,
        pady=4,
        cursor="hand2",
    ).pack(side="left")

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_move)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<ButtonPress-3>", on_escape)
    top.bind("<Escape>", on_escape)
    canvas.bind("<Escape>", on_escape)
    bar.bind("<Escape>", on_escape)
    try:
        ui.root.bind_all("<Escape>", on_escape)
    except tk.TclError:
        pass
    try:
        top.grab_set()
    except tk.TclError:
        pass
    top.update_idletasks()
    _force_activate(top)
    canvas.focus_set()
    ui.root.wait_window(top)
    finish(result["image"])
    return result["image"]
