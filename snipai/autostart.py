"""Open snip-ai at login (Windows Startup folder, Linux autostart)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _windows() -> bool:
    return os.name == "nt"


def is_enabled() -> bool:
    return autostart_path().is_file()


def autostart_path() -> Path:
    if _windows():
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "snip-ai.vbs"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "autostart" / "snip-ai.desktop"


def set_enabled(enabled: bool) -> Path | None:
    path = autostart_path()
    if not enabled:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_script_body(), encoding="utf-8")
    try:
        os.chmod(path, 0o755)
    except OSError:
        pass
    return path


def _script_body() -> str:
    root = project_root()
    if _windows():
        pythonw = Path(sys.executable)
        if pythonw.name.lower() == "python.exe":
            pythonw = pythonw.with_name("pythonw.exe")
        return (
            "Set sh = CreateObject(\"WScript.Shell\")\n"
            f"sh.CurrentDirectory = \"{_vbs_escape(str(root))}\"\n"
            f"sh.Run \"\"\"{_vbs_escape(str(pythonw))}\"\"\" & \" -m snipai run\", 0, False\n"
        )
    exe = Path(sys.executable)
    start = root / "Start.sh"
    command = str(start) if start.is_file() else f"{exe} -m snipai run"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=snip-ai\n"
        f"Exec={command}\n"
        f"Path={root}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def _vbs_escape(value: str) -> str:
    return value.replace('"', '""')
