#!/usr/bin/env bash
# Cross-compile snip-ai.exe (Windows GUI launcher) from Linux or Git Bash.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WIN="$ROOT/scripts/windows"
CC="${CC:-x86_64-w64-mingw32-gcc}"
WINDRES="${WINDRES:-x86_64-w64-mingw32-windres}"
cd "$ROOT"

if ! command -v "$CC" >/dev/null 2>&1; then
  echo "Need MinGW: sudo apt install mingw-w64   (or set CC=)" >&2
  exit 1
fi

PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PY="$ROOT/.venv/bin/python"
  else
    PY="python3"
  fi
fi
"$PY" - <<'PY'
from pathlib import Path
from PIL import Image, ImageDraw

out = Path("scripts/windows/snip-ai.ico")
out.parent.mkdir(parents=True, exist_ok=True)
sizes = [16, 32, 48, 64, 128, 256]
images = []
for s in sizes:
    img = Image.new("RGBA", (s, s), (27, 29, 33, 255))
    draw = ImageDraw.Draw(img)
    m = max(1, s // 16)
    draw.rounded_rectangle((m, m, s - m - 1, s - m - 1), radius=max(2, s // 5), fill=(110, 231, 183, 255))
    x0, y0, x1, y1 = s * 20 // 64, s * 22 // 64, s * 44 // 64, s * 42 // 64
    draw.rectangle((x0, y0, x1, y1), outline=(5, 46, 26, 255), width=max(1, s // 16))
    draw.line((s * 28 // 64, s * 18 // 64, s * 36 // 64, s * 18 // 64), fill=(5, 46, 26, 255), width=max(1, s // 16))
    images.append(img)
images[-1].save(out, format="ICO", sizes=[(s, s) for s in sizes])
print("wrote", out)
PY

"$WINDRES" -I "$WIN" -O coff "$WIN/launcher.rc" -o "$WIN/launcher.res"
"$CC" -O2 -s -mwindows -municode "$WIN/launcher.c" "$WIN/launcher.res" -o "$ROOT/snip-ai.exe" -lshell32 -luser32
echo "wrote $ROOT/snip-ai.exe"
file "$ROOT/snip-ai.exe" || true
ls -l "$ROOT/snip-ai.exe"
