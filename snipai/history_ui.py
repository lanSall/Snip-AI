"""Window listing recent answers with the full text."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

from snipai.clipboard import copy_text
from snipai.history import AnswerHistory, HistoryEntry
from snipai.setup_ui import _bring_to_front

BG = "#1b1d21"
FG = "#f3f4f6"
MUTED = "#9aa3af"
ACCENT = "#6ee7b7"
BORDER = "#2e323a"
BTN_BG = "#2a2f38"
ENTRY_BG = "#111316"

_FONT = ("Segoe UI", 10) if sys.platform == "win32" else ("sans-serif", 10)
_FONT_BOLD = ("Segoe UI", 13, "bold") if sys.platform == "win32" else ("sans-serif", 13, "bold")
_FONT_SMALL = ("Segoe UI", 9) if sys.platform == "win32" else ("sans-serif", 9)
_FONT_MONO = ("Consolas", 10) if sys.platform == "win32" else ("monospace", 10)


def show_history_window(
    history: AnswerHistory,
    *,
    master: tk.Misc,
    select_id: str | None = None,
    window: tk.Toplevel | None = None,
) -> tk.Toplevel:
    """Show or raise the Last answers window. Not modal — hotkeys keep working."""
    if window is not None:
        try:
            if window.winfo_exists():
                _fill(window, history, select_id)
                _bring_to_front(window)
                return window
        except tk.TclError:
            pass

    win = tk.Toplevel(master)
    win.title("snip-ai — Last answers")
    win.configure(bg=BG)
    win.minsize(460, 420)
    try:
        win.geometry("520x520")
    except tk.TclError:
        pass

    outer = tk.Frame(win, bg=BORDER, padx=1, pady=1)
    outer.pack(fill="both", expand=True)
    frame = tk.Frame(outer, bg=BG, padx=18, pady=16)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="Last answers", bg=BG, fg=ACCENT, font=_FONT_BOLD, anchor="w").pack(fill="x")
    tk.Label(
        frame,
        text="The toast only shows a snippet. Full answers live here (last 10).",
        bg=BG,
        fg=MUTED,
        font=_FONT_SMALL,
        anchor="w",
        wraplength=460,
        justify="left",
    ).pack(fill="x", pady=(4, 12))

    list_frame = tk.Frame(frame, bg=BG)
    list_frame.pack(fill="x")
    listbox = tk.Listbox(
        list_frame,
        height=8,
        bg=ENTRY_BG,
        fg=FG,
        selectbackground="#2a2f38",
        selectforeground=ACCENT,
        highlightthickness=0,
        relief="flat",
        font=_FONT,
        activestyle="none",
        exportselection=False,
    )
    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=listbox.yview)
    listbox.configure(yscrollcommand=scroll.set)
    listbox.pack(side="left", fill="x", expand=True)
    scroll.pack(side="right", fill="y")

    body = tk.Text(
        frame,
        wrap="word",
        bg=ENTRY_BG,
        fg=FG,
        insertbackground=FG,
        relief="flat",
        font=_FONT_MONO,
        height=10,
        padx=10,
        pady=10,
        highlightthickness=0,
    )
    body.configure(state="disabled")

    status = tk.StringVar(value="")
    status_label = tk.Label(frame, textvariable=status, bg=BG, fg=MUTED, font=_FONT_SMALL, anchor="w")

    buttons = tk.Frame(frame, bg=BG)

    def current_entry() -> HistoryEntry | None:
        ids: list[str] = getattr(win, "_entry_ids", [])
        try:
            return history.get(ids[listbox.curselection()[0]])
        except Exception:
            return history.entries[0] if history.entries else None

    def show_entry(entry: HistoryEntry | None) -> None:
        body.configure(state="normal")
        body.delete("1.0", "end")
        if entry is None:
            body.insert("1.0", "No answers yet.\n\nPress Ctrl+Shift+Space (or snip) with a question on screen.")
        else:
            body.insert("1.0", entry.full or entry.headline)
        body.configure(state="disabled")

    def on_select(_event: object | None = None) -> None:
        show_entry(current_entry())

    def copy_current() -> None:
        entry = current_entry()
        text = (entry.full or entry.headline) if entry else ""
        if not text:
            status.set("Nothing to copy yet.")
            return
        if copy_text(text):
            status.set("Copied. You can paste it.")
        else:
            status.set("Could not copy. Select the text and copy it yourself.")

    def close() -> None:
        try:
            win.destroy()
        except tk.TclError:
            pass

    tk.Button(
        buttons,
        text="Close",
        command=close,
        bg=BTN_BG,
        fg=FG,
        activebackground="#3a404a",
        activeforeground=FG,
        highlightthickness=0,
        bd=0,
        relief="flat",
        font=_FONT,
        padx=14,
        pady=6,
        cursor="hand2",
    ).pack(side="left")
    tk.Button(
        buttons,
        text="Copy",
        command=copy_current,
        bg=ACCENT,
        fg="#052e1a",
        activebackground="#34d399",
        activeforeground="#052e1a",
        highlightthickness=0,
        bd=0,
        relief="flat",
        font=_FONT,
        padx=14,
        pady=6,
        cursor="hand2",
    ).pack(side="right")

    buttons.pack(side="bottom", fill="x", pady=(10, 0))
    status_label.pack(side="bottom", fill="x")
    body.pack(fill="both", expand=True, pady=(12, 8))

    listbox.bind("<<ListboxSelect>>", on_select)
    win.bind("<Escape>", lambda _e: close())
    win._listbox = listbox  # type: ignore[attr-defined]
    win._show_entry = show_entry  # type: ignore[attr-defined]
    win._history = history  # type: ignore[attr-defined]
    win.protocol("WM_DELETE_WINDOW", close)

    _fill(win, history, select_id)
    _bring_to_front(win)
    return win


def _fill(win: tk.Toplevel, history: AnswerHistory, select_id: str | None) -> None:
    listbox: tk.Listbox = win._listbox  # type: ignore[attr-defined]
    show_entry = win._show_entry  # type: ignore[attr-defined]
    listbox.delete(0, "end")
    ids: list[str] = []
    for entry in history.entries:
        label = f"{entry.when_label()}   {entry.headline}"
        if len(label) > 72:
            label = label[:71] + "…"
        listbox.insert("end", label)
        ids.append(entry.id)
    win._entry_ids = ids  # type: ignore[attr-defined]
    if not ids:
        show_entry(None)
        return
    index = 0
    if select_id:
        try:
            index = ids.index(select_id)
        except ValueError:
            index = 0
    listbox.selection_clear(0, "end")
    listbox.selection_set(index)
    listbox.activate(index)
    listbox.see(index)
    show_entry(history.get(ids[index]))
