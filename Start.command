#!/bin/bash
# Double-click this file on a Mac (or run it from Terminal).
set -euo pipefail
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "snip-ai needs Python 3.10 or newer."
  echo "Install it from https://www.python.org/downloads/ then double-click this file again."
  if command -v open >/dev/null 2>&1; then
    open "https://www.python.org/downloads/"
  fi
  exit 1
fi

exec "$PY" scripts/ensure_and_run.py "$@"
