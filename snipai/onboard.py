"""First-run setup: paste an API key, skip editing YAML."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from snipai.config import (
    KEY_SIGNUP_URLS,
    Config,
    apply_setup,
    load_config,
    needs_setup,
    save_config,
)


def in_automated_run() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CI"))


def can_show_gui() -> bool:
    if sys.platform in {"win32", "darwin"}:
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def should_show_setup_gui() -> bool:
    """Whether to pop the first-run window. Skip pytest/CI so tests do not hang."""
    if not can_show_gui():
        return False
    if in_automated_run():
        return False
    if os.environ.get("SNIPAI_NO_SETUP_GUI") == "1":
        return False
    return True


def run_cli_setup(
    config: Config,
    *,
    stdin=None,
    stdout=None,
) -> Config | None:
    """Ask for an API key in the terminal. Returns None if the user cancels."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    url = KEY_SIGNUP_URLS.get(config.provider.lower(), KEY_SIGNUP_URLS["gemini"])
    print("Welcome to snip-ai.", file=stdout)
    print("Paste an API key, then you can use the hotkeys.", file=stdout)
    print(f"Free Gemini key: {url}", file=stdout)
    print("API key (blank to cancel): ", end="", file=stdout, flush=True)
    try:
        raw = stdin.readline()
    except EOFError:
        return None
    if raw is None:
        return None
    key = raw.strip()
    if not key:
        return None
    return apply_setup(config, api_key=key)


def offer_setup(
    config: Config,
    config_path: Path,
    *,
    force_cli: bool = False,
    always: bool = False,
) -> Config | None:
    """Show the setup window (or a terminal prompt) and save the result.

    Returns the (possibly unchanged) config, or None if the user cancelled.
    """
    if not always and not needs_setup(config):
        return config

    updated: Config | None = None
    gui_attempted = False
    if not force_cli and should_show_setup_gui():
        try:
            from snipai.setup_ui import run_setup_wizard

            updated = run_setup_wizard(config)
            gui_attempted = True
        except Exception as exc:
            import logging

            logging.getLogger("snipai").warning("Setup window failed (%s); trying the terminal.", exc)
            gui_attempted = False
    if updated is None and not gui_attempted and (force_cli or sys.stdin.isatty()):
        if not force_cli and in_automated_run():
            pass
        else:
            updated = run_cli_setup(config)
    if updated is None:
        return None
    save_config(updated, config_path)
    return updated


def load_ready_config(explicit: Path | None, config_path: Path) -> Config | None:
    """Load settings, running first-run setup when no API key is present."""
    config = load_config(explicit)
    if not needs_setup(config):
        return config
    return offer_setup(config, config_path)
