"""Simple setup window: paste a key, pick a model, click Save."""

from __future__ import annotations

import sys
import tkinter as tk
import webbrowser
from tkinter import ttk

from snipai.config import KEY_SIGNUP_URLS, Config, apply_setup, models_for_provider
from snipai.hotkeys import (
    format_binding,
    normalize_binding,
    start_shortcut_capture,
    validate_binding,
)

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


def run_setup_wizard(
    config: Config,
    *,
    master: tk.Misc | None = None,
    running: bool = False,
) -> Config | None:
    """Blocking setup window. Returns an updated config, or None if cancelled.

    When ``master`` is a live Tk root (app already running), the window is a
    Toplevel so it can share that loop.
    """
    result: dict[str, Config | None] = {"config": None}
    owns_root = master is None
    root: tk.Misc = tk.Tk() if owns_root else tk.Toplevel(master)
    if not owns_root and master is not None and sys.platform == "win32":
        # Pulse the hidden toast root so Windows actually maps this Toplevel.
        try:
            master.deiconify()
            master.withdraw()
        except tk.TclError:
            pass
    root.title("snip-ai settings" if running else "snip-ai setup")
    root.configure(bg=BG)
    try:
        root.resizable(True, True)
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

    heading = "snip-ai settings" if running else "snip-ai"
    blurb = (
        "Change your API key, model, or shortcuts here. After Save, they apply right away."
        if running
        else "Paste an API key, pick a model, then a hotkey sends whatever is\n"
        "on screen to AI and shows a tiny answer."
    )
    tk.Label(frame, text=heading, bg=BG, fg=ACCENT, font=_FONT_BOLD, anchor="w").pack(fill="x")
    tk.Label(
        frame,
        text=blurb,
        bg=BG,
        fg=MUTED,
        font=_FONT,
        justify="left",
        anchor="w",
        wraplength=420,
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

    tk.Label(frame, text="Model", bg=BG, fg=FG, font=_FONT, anchor="w").pack(fill="x")
    model_combo = ttk.Combobox(frame, state="readonly", font=_FONT)
    model_combo.pack(fill="x", pady=(4, 12))

    def fill_models(provider: str, current: str) -> None:
        choices = list(models_for_provider(provider))
        ids_m = [mid for mid, _label in choices]
        labels_m = [label for _mid, label in choices]
        if current and current not in ids_m:
            ids_m.append(current)
            labels_m.append(current)
        model_combo.configure(values=labels_m)
        model_combo._ids = ids_m  # type: ignore[attr-defined]
        try:
            model_combo.current(ids_m.index(current) if current in ids_m else 0)
        except Exception:
            if labels_m:
                model_combo.current(0)

    def selected_model() -> str:
        ids_m = getattr(model_combo, "_ids", [])
        try:
            return ids_m[model_combo.current()]
        except Exception:
            choices = models_for_provider(selected_provider())
            return choices[0][0] if choices else config.model

    fill_models(selected_provider(), config.model)

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
        show="*",
    )
    entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

    def toggle_key() -> None:
        show_key.set(not show_key.get())
        entry.configure(show="" if show_key.get() else "*")
        peek.configure(text="Hide" if show_key.get() else "Show")

    peek = tk.Button(
        key_row,
        text="Show",
        command=toggle_key,
        bg=BTN_BG,
        fg=FG,
        activebackground="#3a404a",
        activeforeground=FG,
        highlightthickness=0,
        bd=0,
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
        activebackground=BG,
        activeforeground=ACCENT,
        highlightthickness=0,
        bd=0,
        relief="flat",
        font=_FONT_SMALL,
        cursor="hand2",
        anchor="w",
    )
    link.pack(fill="x", pady=(4, 8))

    tk.Label(frame, text="Shortcuts", bg=BG, fg=FG, font=_FONT, anchor="w").pack(fill="x", pady=(8, 0))
    tk.Label(
        frame,
        text="Click Change, then press a key combo or a mouse side / middle button.\n"
        "Left click cannot be a shortcut.",
        bg=BG,
        fg=MUTED,
        font=_FONT_SMALL,
        anchor="w",
        justify="left",
    ).pack(fill="x", pady=(2, 8))

    shortcut_specs = (
        ("hotkey", "Screen", config.hotkey),
        ("region_hotkey", "Snip", config.region_hotkey),
        ("ask_hotkey", "Ask", config.ask_hotkey),
        ("settings_hotkey", "Settings", config.settings_hotkey),
    )
    shortcut_vars: dict[str, tk.StringVar] = {}
    shortcut_labels: dict[str, tk.Label] = {}
    shortcut_buttons: dict[str, tk.Button] = {}
    capturing: dict[str, object] = {"id": None, "stop": None}

    def show_shortcut(action: str) -> None:
        label = shortcut_labels.get(action)
        if label is None:
            return
        if capturing["id"] == action:
            label.configure(text="Press a key or mouse button…")
            return
        label.configure(text=format_binding(shortcut_vars[action].get()))

    def abort_capture() -> None:
        stop = capturing["stop"]
        capturing["stop"] = None
        old = capturing["id"]
        capturing["id"] = None
        if callable(stop):
            try:
                stop()
            except Exception:
                pass
        if old:
            show_shortcut(str(old))
            btn = shortcut_buttons.get(str(old))
            if btn is not None:
                btn.configure(text="Change")

    def apply_captured(action: str, value: str | None) -> None:
        capturing["stop"] = None
        capturing["id"] = None
        btn = shortcut_buttons.get(action)
        if btn is not None:
            btn.configure(text="Change")
        if not value:
            show_shortcut(action)
            return
        err = validate_binding(value)
        if err:
            error_var.set(err)
            show_shortcut(action)
            return
        shortcut_vars[action].set(value)
        error_var.set("")
        show_shortcut(action)

    def begin_capture(action: str) -> None:
        if capturing["id"] == action:
            abort_capture()
            return
        abort_capture()
        capturing["id"] = action
        shortcut_buttons[action].configure(text="Cancel")
        show_shortcut(action)

        def captured(value: str | None, which: str = action) -> None:
            try:
                root.after(0, lambda v=value: apply_captured(which, v))
            except tk.TclError:
                pass

        try:
            capturing["stop"] = start_shortcut_capture(captured)
        except Exception as exc:
            capturing["id"] = None
            shortcut_buttons[action].configure(text="Change")
            show_shortcut(action)
            error_var.set(f"Could not listen for a shortcut: {exc}")

    for action, title, current in shortcut_specs:
        shortcut_vars[action] = tk.StringVar(value=current)
        row = tk.Frame(frame, bg=BG)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=title, bg=BG, fg=FG, font=_FONT, width=10, anchor="w").pack(side="left")
        shown = tk.Label(
            row,
            text=format_binding(current),
            bg=ENTRY_BG,
            fg=FG,
            font=_FONT,
            anchor="w",
            padx=10,
            pady=6,
        )
        shown.pack(side="left", fill="x", expand=True, padx=(0, 8))
        shortcut_labels[action] = shown
        change = tk.Button(
            row,
            text="Change",
            command=lambda a=action: begin_capture(a),
            bg=BTN_BG,
            fg=FG,
            activebackground="#3a404a",
            activeforeground=FG,
            highlightthickness=0,
            bd=0,
            relief="flat",
            font=_FONT_SMALL,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        change.pack(side="right")
        shortcut_buttons[action] = change

    tk.Label(frame, textvariable=error_var, bg=BG, fg=DANGER, font=_FONT_SMALL, anchor="w").pack(fill="x")

    def refresh_provider(_event: object | None = None) -> None:
        provider = selected_provider()
        provider_var.set(provider)
        fill_models(provider, selected_model() if provider == config.provider else "")
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

    combo.bind("<<ComboboxSelected>>", refresh_provider)

    def save_and_close() -> None:
        abort_capture()
        provider = selected_provider()
        key = key_var.get().strip()
        if provider != "ollama" and not key:
            error_var.set("Paste a key, or choose Ollama if you run a model locally.")
            return
        chosen: dict[str, str] = {}
        for action, _title, _current in shortcut_specs:
            raw = shortcut_vars[action].get().strip()
            err = validate_binding(raw)
            if err:
                error_var.set(f"{_title}: {err}")
                return
            chosen[action] = normalize_binding(raw)
        seen: dict[str, str] = {}
        for action, title, _current in shortcut_specs:
            bound = chosen[action]
            if bound in seen:
                error_var.set(f"{title} and {seen[bound]} cannot share the same shortcut.")
                return
            seen[bound] = title
        updated = apply_setup(
            config, api_key=key, provider=provider, model=selected_model()
        )
        updated.hotkey = chosen["hotkey"]
        updated.region_hotkey = chosen["region_hotkey"]
        updated.ask_hotkey = chosen["ask_hotkey"]
        updated.settings_hotkey = chosen["settings_hotkey"]
        result["config"] = updated
        root.destroy()

    def cancel() -> None:
        abort_capture()
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
        text="Save" if running else "Save and start",
        command=save_and_close,
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

    root._hotkeys = shortcut_vars  # type: ignore[attr-defined]
    root._save = save_and_close  # type: ignore[attr-defined]
    root._cancel = cancel  # type: ignore[attr-defined]

    root.protocol("WM_DELETE_WINDOW", cancel)
    entry.focus_set()
    root.update_idletasks()
    width = max(root.winfo_reqwidth(), 520)
    height = root.winfo_reqheight()
    screen_h = root.winfo_screenheight()
    height = min(height, max(420, screen_h - 80))
    x = max(0, (root.winfo_screenwidth() - width) // 2)
    y = max(0, (screen_h - height) // 3)
    try:
        root.geometry(f"{width}x{height}+{x}+{y}")
    except tk.TclError:
        pass
    _bring_to_front(root)
    if owns_root:
        root.mainloop()
        try:
            root.destroy()
        except tk.TclError:
            pass
    else:
        master.wait_window(root)  # type: ignore[union-attr]
    return result["config"]


def _bring_to_front(win: tk.Misc) -> None:
    """Show a dialog above other windows. Needed after a tray click on Windows."""
    try:
        win.deiconify()
    except tk.TclError:
        pass
    try:
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        win.update()
    except tk.TclError:
        pass
    if sys.platform == "win32":
        try:
            import ctypes

            hwnd = int(win.winfo_id())
            user32 = ctypes.windll.user32
            parent = user32.GetParent(hwnd)
            if parent:
                hwnd = parent
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
        except Exception:
            pass
    try:
        def _clear_topmost() -> None:
            try:
                win.attributes("-topmost", False)
            except tk.TclError:
                pass

        win.after(400, _clear_topmost)
    except tk.TclError:
        pass


def _provider_or_gemini(provider: str) -> str:
    known = {pid for pid, _label in PROVIDERS}
    value = (provider or "gemini").lower().strip()
    if value == "google":
        return "gemini"
    return value if value in known else "gemini"
