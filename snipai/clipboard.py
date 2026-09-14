"""Copy the full answer so it can be pasted without extra clicks."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

log = logging.getLogger("snipai")


def copy_text(text: str) -> bool:
    """Copy ``text`` to the clipboard. Returns False if every backend failed."""
    if not text:
        return False
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception as exc:
        log.debug("pyperclip copy failed: %s", exc)

    if sys.platform == "darwin":
        return _run(["pbcopy"], text)
    if sys.platform.startswith("linux"):
        if shutil.which("xclip"):
            return _run(["xclip", "-selection", "clipboard"], text)
        if shutil.which("xsel"):
            return _run(["xsel", "--clipboard", "--input"], text)
        return False
    if sys.platform == "win32":
        return _run(["clip"], text)
    return False


def _run(command: list[str], text: str) -> bool:
    try:
        subprocess.run(command, input=text, text=True, check=True, timeout=3)
        return True
    except Exception as exc:
        log.debug("clipboard command %s failed: %s", command, exc)
        return False
