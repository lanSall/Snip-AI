"""Create a local Python environment if needed, then start snip-ai."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def _ok(python: Path) -> bool:
    if not python.is_file():
        return False
    result = subprocess.run(
        [str(python), "-c", "import snipai, yaml, mss, PIL"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _install(python: Path) -> None:
    subprocess.check_call(
        [str(python), "-m", "pip", "install", "-e", str(ROOT), "-q"],
        cwd=str(ROOT),
    )


def _create_venv() -> None:
    print("First launch: installing snip-ai (this takes a minute)…", flush=True)
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    _install(_venv_python())


def _tk_hint() -> str | None:
    python = _venv_python()
    result = subprocess.run([str(python), "-c", "import tkinter"], capture_output=True, text=True)
    if result.returncode == 0:
        return None
    if sys.platform == "darwin":
        return "Python is missing Tk. Install Python from python.org, or run: brew install python-tk"
    if os.name == "nt":
        return "Python is missing Tk. Reinstall from python.org and leave the tcl/tk option enabled."
    return "Python is missing Tk. On Ubuntu/Debian run:  sudo apt install python3-tk"


def main() -> int:
    os.chdir(ROOT)
    python = _venv_python()
    if not python.is_file() or not _ok(python):
        try:
            _create_venv()
        except subprocess.CalledProcessError as exc:
            print(f"Could not install snip-ai (exit {exc.returncode}).", file=sys.stderr)
            print("You need Python 3.10 or newer from https://www.python.org/downloads/", file=sys.stderr)
            if sys.platform.startswith("linux"):
                print("On Ubuntu/Debian:  sudo apt install python3 python3-venv python3-dev python3-tk", file=sys.stderr)
            return exc.returncode or 1
        python = _venv_python()
    else:
        # Reinstall from this folder so `git pull` actually updates the running app.
        try:
            _install(python)
        except subprocess.CalledProcessError as exc:
            print(f"Could not update snip-ai (exit {exc.returncode}). Trying a clean install…", file=sys.stderr)
            try:
                _create_venv()
            except subprocess.CalledProcessError as recreate:
                print(f"Could not install snip-ai (exit {recreate.returncode}).", file=sys.stderr)
                return recreate.returncode or exc.returncode or 1
            python = _venv_python()

    hint = _tk_hint()
    if hint:
        print(hint, file=sys.stderr)
        return 1

    extra = sys.argv[1:]
    command = extra[0] if extra else "run"
    keep_console = os.environ.get("SNIPAI_CONSOLE") == "1" or command != "run"
    if os.name == "nt" and not keep_console:
        pythonw = python.with_name("pythonw.exe")
        if pythonw.is_file():
            subprocess.Popen(
                [str(pythonw), "-m", "snipai", *extra],
                cwd=str(ROOT),
                close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return 0
    return subprocess.call([str(python), "-m", "snipai", *extra])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nbye")
        raise SystemExit(0)
