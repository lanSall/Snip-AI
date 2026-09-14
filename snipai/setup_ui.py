"""Simple first-run window: paste a key, click Save, start capturing."""

from __future__ import annotations

import sys
import tkinter as tk
import webbrowser
from tkinter import ttk

from snipai.config import KEY_SIGNUP_URLS, Config, apply_setup

BG = "#1b1d21"
FG = "#f3f4f6"
MUTED = "#9aa3af"
ACCENT = "#6ee7b7"
BORDER = "#2e323a"
BTN_BG = "#2a2f38"
ENTRY_BG = "#111316"
DANGER = "#f87171"

PROVIDERS = (
    ("gemini", "Google Gemini (recommended)"),
    ("openai", "OpenAI"),
    ("anthropic", "Anthropic Claude"),
    ("openrouter", "OpenRouter"),
    ("ollama", "Ollama (runs on this computer, no key)"),
)

_FONT = ("Segoe UI", 10) if sys.platform == "win32" else ("sans-serif", 10)
_FONT_BOLD = ("Segoe UI", 14, "bold") if sys.platform == "win32" else ("sans-serif", 14, "bold")
_FONT_SMALL = ("Segoe UI", 9) if sys.platform == "win32" else ("sans-serif", 9)


def run_setup_wizard(config: Config) -> Config | None:
    """Blocking setup window. Returns an updated config, or None if cancelled."""
    result: dict[str, Config | None] = {"config": None}

    root = tk.Tk()
    root.title("snip-ai setup")
    root.configure(bg=BG)
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass

    provider_var = tk.StringVar(value=_provider_or_gemini(config.provider))
    key_var = tk.StringVar(value=config.api_key)
    error_var = tk.StringVar(value="")
    show_key = tk.BooleanVar(value=False)

    outer = tk.Frame(root, bg=BORDER, padx=1, pady=1)
    outer.pack(fill="both", expand=True)
    frame = tk.Frame(outer, bg=BG, padx=28, pady=24)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="snip-ai", bg=BG, fg=ACCENT, font=_FONT_BOLD, anchor="w").pack(fill="x")
    tk.Label(
        frame,
        text="Paste an API key once. After that, a hotkey sends\n"
        "whatever is on screen to AI and shows a tiny answer.",
        bg=BG,
        fg=MUTED,
        font=_FONT,
        justify="left",
        anchor="w",
    ).pack(fill="x", pady=(8, 18))

    tk.Label(frame, text="Which AI?", bg=BG, fg=FG, font=_FONT, anchor="w").pack(fill="x")
    labels = [label for _id, label in PROVIDERS]
    ids = [pid for pid, _label in PROVIDERS]
    combo = ttk.Combobox(frame, values=labels, state="readonly", font=_FONT)
    combo.pack(fill="x", pady=(4, 12))
    try:
        combo.current(ids.index(provider_var.get()))
    except ValueError:
        combo.current(0)
        provider_var.set("gemini")

    def selected_provider() -> str:
        try:
            return ids[combo.current()]
        except Exception:
            return "gemini"

    tk.Label(frame, text="API key", bg=BG, fg=FG, font=_FONT, anchor="w").pack(fill="x")
    key_row = tk.Frame(frame, bg=BG)
    key_row.pack(fill="x", pady=(4, 4))
    entry = tk.Entry(
        key_row,
        textvariable=key_var,
        font=_FONT,
        bg=ENTRY_BG,
        fg=FG,
        insertbackground=FG,
        relief="flat",
        show="•",
    )
    entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

    def toggle_key() -> None:
        show_key.set(not show_key.get())
        entry.configure(show="" if show_key.get() else "•")
        peek.configure(text="Hide" if show_key.get() else "Show")

    peek = tk.Button(
        key_row,
        text="Show",
        command=toggle_key,
        bg=BTN_BG,
        fg=FG,
        relief="flat",
        font=_FONT_SMALL,
        padx=8,
        cursor="hand2",
    )
    peek.pack(side="right")

    def open_key_page() -> None:
        url = KEY_SIGNUP_URLS.get(selected_provider(), KEY_SIGNUP_URLS["gemini"])
        webbrowser.open(url)

    link = tk.Button(
        frame,
        text="Get a free Gemini key — opens in your browser",
        command=open_key_page,
        bg=BG,
        fg=ACCENT,
        relief="flat",
        font=_FONT_SMALL,
        cursor="hand2",
        anchor="w",
    )
    link.pack(fill="x", pady=(4, 8))

    tk.Label(frame, textvariable=error_var, bg=BG, fg=DANGER, font=_FONT_SMALL, anchor="w").pack(fill="x")

    def refresh_link(_event: object | None = None) -> None:
        provider = selected_provider()
        provider_var.set(provider)
        if provider == "ollama":
            link.configure(text="How to install Ollama — opens in your browser")
            error_var.set("")
        elif provider == "openai":
            link.configure(text="Get an OpenAI key — opens in your browser")
        elif provider == "anthropic":
            link.configure(text="Get an Anthropic key — opens in your browser")
        elif provider == "openrouter":
            link.configure(text="Get an OpenRouter key — opens in your browser")
        else:
            link.configure(text="Get a free Gemini key — opens in your browser")

    combo.bind("<<ComboboxSelected>>", refresh_link)

    def save_and_close() -> None:
        provider = selected_provider()
        key = key_var.get().strip()
        if provider != "ollama" and not key:
            error_var.set("Paste a key, or choose Ollama if you run a model locally.")
            return
        result["config"] = apply_setup(config, api_key=key, provider=provider)
        root.destroy()

    def cancel() -> None:
        result["config"] = None
        root.destroy()

    buttons = tk.Frame(frame, bg=BG)
    buttons.pack(fill="x", pady=(16, 0))
    tk.Button(
        buttons,
        text="Cancel",
        command=cancel,
        bg=BTN_BG,
        fg=FG,
        relief="flat",
        font=_FONT,
        padx=14,
        pady=6,
        cursor="hand2",
    ).pack(side="left")
    tk.Button(
        buttons,
        text="Save and start",
        command=save_and_close,
        bg=ACCENT,
        fg="#052e1a",
        relief="flat",
        font=_FONT,
        padx=14,
        pady=6,
        cursor="hand2",
    ).pack(side="right")

    tk.Label(
        frame,
        text="Ctrl+Shift+Space  whole screen    ·    Ctrl+Shift+.  draw a box",
        bg=BG,
        fg=MUTED,
        font=_FONT_SMALL,
        anchor="w",
    ).pack(fill="x", pady=(18, 0))

    root.protocol("WM_DELETE_WINDOW", cancel)
    entry.focus_set()
    root.update_idletasks()
    width, height = root.winfo_reqwidth(), root.winfo_reqheight()
    x = max(0, (root.winfo_screenwidth() - width) // 2)
    y = max(0, (root.winfo_screenheight() - height) // 3)
    root.geometry(f"+{x}+{y}")
    try:
        root.lift()
        root.focus_force()
    except tk.TclError:
        pass
    root.mainloop()
    try:
        root.destroy()
    except tk.TclError:
        pass
    return result["config"]


def _provider_or_gemini(provider: str) -> str:
    known = {pid for pid, _label in PROVIDERS}
    value = (provider or "gemini").lower().strip()
    if value == "google":
        return "gemini"
    return value if value in known else "gemini"
