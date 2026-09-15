import os

import pytest

from snipai.capture import prepare_png, snapshot_current
from snipai.config import NotifyConfig
from snipai.ui import ToastUI


pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY") and os.name != "nt", reason="needs a display")


def test_list_and_grab_current_monitor():
    monitor, image = snapshot_current()
    assert monitor.width > 0 and monitor.height > 0
    assert image.size[0] > 0 and image.size[1] > 0
    png = prepare_png(image, max_width=800)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_toast_does_not_crash():
    ui = ToastUI(NotifyConfig(duration_ms=50, position="bottom-right"))
    try:
        ui.show_toast("Answer", "408")
        ui.root.update()
        assert ui._toast is not None
        ui._close_toast()
        ui.root.update()
        assert ui._toast is None
    finally:
        ui.destroy()


def test_schedule_runs_on_tk_pump():
    ui = ToastUI(NotifyConfig(duration_ms=50))
    try:
        seen: list[str] = []
        ui.schedule(lambda: seen.append("ok"))
        ui._pump_jobs()
        ui.root.update()
        assert seen == ["ok"]
    finally:
        ui.destroy()


def test_select_region_escape_cancels():
    from PIL import Image

    from snipai.ui import select_region

    ui = ToastUI(NotifyConfig(duration_ms=50))
    image = Image.new("RGB", (320, 200), color=(30, 30, 30))
    seen: dict[str, object] = {}

    def start() -> None:
        def hit_escape() -> None:
            overlay = ui._snip_overlay
            if overlay is not None:
                overlay.event_generate("<Escape>")
            else:
                ui.cancel_snip()

        ui.root.after(200, hit_escape)
        seen["crop"] = select_region(ui, image, 0, 0)
        ui.root.quit()

    try:
        ui.root.after(20, start)
        ui.root.mainloop()
        assert seen.get("crop") is None
        assert getattr(ui, "_snip_overlay", None) is None
    finally:
        ui.destroy()


def test_history_window_lists_entry():
    from snipai.history import AnswerHistory
    from snipai.history_ui import show_history_window

    ui = ToastUI(NotifyConfig(duration_ms=50))
    hist = AnswerHistory()
    hist.add("408", "ANSWER: 408\nWHY: 17 times 24.")
    try:
        win = show_history_window(hist, master=ui.root)
        ui.root.update()
        assert "408" in win._listbox.get(0)
        win.destroy()
    finally:
        ui.destroy()


def test_cancel_snip_closes_overlay():
    import tkinter as tk

    ui = ToastUI(NotifyConfig(duration_ms=50))
    try:
        overlay = tk.Toplevel(ui.root)
        ui._snip_overlay = overlay
        ui.cancel_snip()
        ui.root.update()
        assert ui._snip_overlay is None
    finally:
        ui.destroy()


def test_ask_window_submits_text():
    from snipai.ui import show_ask_window

    ui = ToastUI(NotifyConfig(duration_ms=50))
    seen: dict[str, str] = {}

    def on_submit(question: str) -> None:
        seen["q"] = question

    try:
        win = show_ask_window(ui, on_submit)
        ui.root.update()
        win._entry.insert("1.0", "What is 2+2?")
        win._submit()
        ui.root.update()
        assert seen.get("q") == "What is 2+2?"
        assert not win.winfo_exists()
    finally:
        ui.destroy()


def test_ask_window_escape_cancels():
    from snipai.ui import show_ask_window

    ui = ToastUI(NotifyConfig(duration_ms=50))
    seen: dict[str, str] = {}

    def on_submit(question: str) -> None:
        seen["q"] = question

    try:
        win = show_ask_window(ui, on_submit)
        ui.root.update()
        win._entry.insert("1.0", "should not send")
        win._cancel()
        ui.root.update()
        assert "q" not in seen
        assert not win.winfo_exists()
    finally:
        ui.destroy()


def test_ask_window_empty_stays_open():
    from snipai.ui import show_ask_window

    ui = ToastUI(NotifyConfig(duration_ms=50))
    seen: dict[str, str] = {}

    def on_submit(question: str) -> None:
        seen["q"] = question

    try:
        win = show_ask_window(ui, on_submit)
        ui.root.update()
        win._submit()
        ui.root.update()
        assert "q" not in seen
        assert win.winfo_exists()
        win._cancel()
    finally:
        ui.destroy()
