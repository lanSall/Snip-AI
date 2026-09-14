"""CLI: ``python -m snipai`` / ``snip-ai``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from snipai import SnipError, __version__
from snipai.app import SnipApp
from snipai.capture import image_from_png, prepare_png, snapshot_current
from snipai.config import default_config_path, load_config, resolve_config_path, user_data_dir, write_example_config
from snipai.solver import make_solver
from snipai.ui import ToastUI, configure_dpi, select_region


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

    init = sub.add_parser("init", help="Write a starter config file.")
    init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing config with the example file.",
    )

    test = sub.add_parser("test-notify", help="Show a sample toast (no screenshot / API).")
    test.add_argument("message", nargs="?", default="ANSWER: 42\nWHY: Sample notification from snip-ai.")

    args = parser.parse_args(argv)
    command = args.command or "run"
    _setup_logging()
    configure_dpi()

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
    if path.exists() and args.force:
        path.unlink()
    written = write_example_config(path)
    print(f"Wrote {written}")
    print("Add your API key, then run: snip-ai run")
    return 0


def _cmd_test_notify(args: argparse.Namespace) -> int:
    from snipai.config import NotifyConfig
    from snipai.formatting import toast_body

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

    def show_toast(self, title: str, body: str, *, duration_ms: int | None = None) -> None:
        return None

    def destroy(self) -> None:
        return None


def _cmd_with_config(command: str, args: argparse.Namespace) -> int:
    config_path = resolve_config_path(args.config)
    config = load_config(args.config)
    solver = make_solver(config)
    notify = not getattr(args, "no_notify", False)

    if command == "run":
        ui = ToastUI(config.notify)
        app = SnipApp(config, solver, ui)
        print(
            f"snip-ai {__version__}  ·  {config.hotkey} current screen  ·  "
            f"{config.region_hotkey} region snip  ·  Ctrl+C to quit",
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
                "snip-ai: no API key. Edit the config file above and set api_key, "
                "or set GEMINI_API_KEY / OPENAI_API_KEY / SNIPAI_API_KEY.",
                file=sys.stderr,
            )
        try:
            app.run_hotkeys()
        except KeyboardInterrupt:
            print("\nbye")
        finally:
            ui.destroy()
        return 0

    if command == "once":
        ui = ToastUI(config.notify)
        app = SnipApp(config, solver, ui)
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
        ui = ToastUI(config.notify) if notify else _HeadlessUI()
        app = SnipApp(config, solver, ui)
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


def _setup_logging() -> None:
    log_dir = user_data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "snip-ai.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


if __name__ == "__main__":
    sys.exit(main())
