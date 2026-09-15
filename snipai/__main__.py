"""CLI: ``python -m snipai`` / ``snip-ai``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from snipai import SnipError, __version__
from snipai.app import SnipApp
from snipai.capture import image_from_png, prepare_png, snapshot_current
from snipai.config import (
    apply_setup,
    default_config_path,
    load_config,
    resolve_config_path,
    save_config,
    user_data_dir,
    write_example_config,
)
from snipai.history import AnswerHistory
from snipai.onboard import in_automated_run, load_ready_config, offer_setup, should_show_setup_gui
from snipai.solver import make_solver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="snip-ai",
        description="Hotkey-capture the current screen, solve it with a vision model, and show a discreet answer toast.",
    )
    parser.add_argument("--version", action="version", version=f"snip-ai {__version__}")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: platform config dir, or $SNIPAI_CONFIG).",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="Start the background hotkey listener (default).")

    once = sub.add_parser("once", help="Capture now, solve, and notify.")
    once.add_argument(
        "--region",
        action="store_true",
        help="Drag a rectangle instead of capturing the whole current monitor.",
    )
    once.add_argument("--no-notify", action="store_true", help="Print the answer only; skip the toast.")

    solve = sub.add_parser("solve", help="Solve an existing image file.")
    solve.add_argument("image", type=Path)
    solve.add_argument("--no-notify", action="store_true", help="Print the answer only; skip the toast.")

    init = sub.add_parser("init", help="Paste your API key (setup window, or --key).")
    init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing config with the example file.",
    )
    init.add_argument("--key", default="", help="Save this API key and skip the setup window.")
    init.add_argument(
        "--provider",
        default="",
        help="gemini (default), openai, anthropic, openrouter, or ollama.",
    )
    init.add_argument("--cli", action="store_true", help="Prompt in the terminal instead of a window.")

    test = sub.add_parser("test-notify", help="Show a sample toast (no screenshot / API).")
    test.add_argument("message", nargs="?", default="ANSWER: 42\nWHY: Sample notification from snip-ai.")

    args = parser.parse_args(argv)
    command = args.command or "run"
    _setup_logging()
    try:
        from snipai.ui import configure_dpi

        configure_dpi()
    except ModuleNotFoundError:
        pass

    try:
        if command == "init":
            return _cmd_init(args)
        if command == "test-notify":
            return _cmd_test_notify(args)
        return _cmd_with_config(command, args)
    except SnipError as exc:
        print(f"snip-ai: {exc}", file=sys.stderr)
        return 1


def _cmd_init(args: argparse.Namespace) -> int:
    path = args.config or default_config_path()
    existing = load_config(path)

    if args.key.strip():
        saved = save_config(apply_setup(existing, api_key=args.key, provider=args.provider or None), path)
        print(f"Saved {saved}")
        print("You can start with: snip-ai")
        return 0

    if args.force:
        if path.exists():
            path.unlink()
        written = write_example_config(path)
        print(f"Wrote {written}")
        print("Paste your API key in that file, or run snip-ai and use the setup window.")
        return 0

    if args.cli or (not in_automated_run() and (should_show_setup_gui() or sys.stdin.isatty())):
        updated = offer_setup(existing, path, force_cli=args.cli, always=True)
        if updated is None:
            print("Setup cancelled.")
            return 1
        print(f"Saved {path}")
        print("You can start with: snip-ai")
        return 0

    written = write_example_config(path)
    print(f"Wrote {written}")
    print("Double-click Start (or run snip-ai) and paste your API key in the window.")
    return 0


def _require_tk() -> None:
    try:
        import tkinter  # noqa: F401
    except ModuleNotFoundError:
        hint = "On Ubuntu/Debian: sudo apt install python3-tk"
        if sys.platform == "win32":
            hint = "Reinstall Python from python.org and leave the tcl/tk option enabled."
        elif sys.platform == "darwin":
            hint = "Install Python from python.org, or: brew install python-tk"
        raise SnipError(f"Python is missing Tk (the window toolkit). {hint}") from None


def _cmd_test_notify(args: argparse.Namespace) -> int:
    from snipai.config import NotifyConfig
    from snipai.formatting import toast_body
    _require_tk()
    from snipai.ui import ToastUI
    ui = ToastUI(NotifyConfig(duration_ms=4000))
    ui.show_toast("Answer", toast_body(args.message))
    ui.root.after(4500, ui.root.quit)
    ui.mainloop()
    ui.destroy()
    return 0


class _HeadlessUI:
    """Used when the caller only wants stdout (tests / scripts)."""

    def schedule(self, fn) -> None:
        fn()

    def show_toast(
        self, title: str, body: str, *, duration_ms: int | None = None, on_click=None
    ) -> None:
        return None

    def destroy(self) -> None:
        return None


def _cmd_with_config(command: str, args: argparse.Namespace) -> int:
    config_path = resolve_config_path(args.config)
    config = load_ready_config(args.config, config_path)
    if config is None:
        print(
            "snip-ai: setup cancelled. Run snip-ai again and paste an API key,\n"
            "  or: snip-ai init --key YOUR_KEY",
            file=sys.stderr,
        )
        return 1
    solver = make_solver(config)
    notify = not getattr(args, "no_notify", False)
    history = _make_history()

    if command == "run":
        _require_tk()
        from snipai.ui import ToastUI
        from snipai.tray import start_tray, tray_available

        ui = ToastUI(config.notify)
        app = SnipApp(config, solver, ui, config_path=config_path, history=history)
        print(
            f"snip-ai {__version__}  ·  {config.hotkey} current screen  ·  "
            f"{config.region_hotkey} region snip  ·  {config.ask_hotkey} ask  ·  "
            f"{config.settings_hotkey} settings",
            flush=True,
        )
        exists = config_path.is_file()
        print(
            f"config  {config_path}" + ("" if exists else "  (not found — using defaults)"),
            flush=True,
        )
        print(f"model   {config.provider} / {config.model}", flush=True)
        if config.provider.lower() != "mock" and not config.resolved_api_key():
            print(
                "snip-ai: no API key. Run snip-ai again to open setup, "
                "or: snip-ai init --key YOUR_KEY",
                file=sys.stderr,
            )
        icon = None
        if tray_available():

            def on_quit() -> None:
                quit_fn = getattr(ui, "quit", None)
                if callable(quit_fn):
                    quit_fn()
                else:
                    ui.destroy()

            icon = start_tray(
                on_settings=app.open_settings,
                on_history=app.open_history,
                on_ask=app.open_ask,
                on_quit=on_quit,
            )
        try:
            app.run_hotkeys()
        except KeyboardInterrupt:
            print("\nbye")
        finally:
            if icon is not None:
                try:
                    icon.stop()
                except Exception:
                    pass
            ui.destroy()
        return 0

    if command == "once":
        _require_tk()
        from snipai.ui import ToastUI, select_region
        ui = ToastUI(config.notify)
        app = SnipApp(config, solver, ui, history=history)
        mode = "region" if args.region or config.capture_mode == "region" else "screen"
        try:
            if mode == "region":
                monitor, image = snapshot_current()
                cropped = select_region(ui, image, monitor.left, monitor.top)
                if cropped is None:
                    print("Cancelled.")
                    return 0
                png = prepare_png(cropped, max_width=config.max_image_width)
            else:
                _monitor, image = snapshot_current()
                png = prepare_png(image, max_width=config.max_image_width)
            answer = app.solve_png(png, notify=notify)
            print(answer)
            if notify:
                ui.root.after(config.notify.duration_ms + 200, ui.root.quit)
                ui.mainloop()
        finally:
            ui.destroy()
        return 0

    if command == "solve":
        image_path: Path = args.image
        if not image_path.exists():
            raise SnipError(f"Image not found: {image_path}")
        png = prepare_png(image_from_png(image_path.read_bytes()), max_width=config.max_image_width)
        if notify:
            _require_tk()
            from snipai.ui import ToastUI

            ui = ToastUI(config.notify)
        else:
            ui = _HeadlessUI()
        app = SnipApp(config, solver, ui, history=history)
        try:
            answer = app.solve_png(png, notify=notify)
            print(answer)
            if notify:
                ui.root.after(config.notify.duration_ms + 200, ui.root.quit)
                ui.mainloop()
        finally:
            ui.destroy()
        return 0

    raise SnipError(f"Unknown command: {command}")


def _make_history() -> AnswerHistory:
    if in_automated_run():
        return AnswerHistory()
    return AnswerHistory(user_data_dir() / "answers.json")


def _setup_logging() -> None:
    log_dir = user_data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "snip-ai.log"
    handlers: list[logging.Handler] = [logging.FileHandler(log_path, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


if __name__ == "__main__":
    sys.exit(main())
