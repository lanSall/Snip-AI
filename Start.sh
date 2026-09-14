#!/bin/bash
# Linux launcher — run this, or double-click it if your file manager allows.
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "snip-ai needs Python 3.10 or newer (python3)."
  echo "On Ubuntu/Debian:  sudo apt install python3 python3-venv python3-dev python3-tk"
  exit 1
fi

exec "$PY" scripts/ensure_and_run.py "$@"
