#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

for command in node npm python3; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'Aria requires %s. Install it, then run this script again.\n' "$command" >&2
    exit 1
  fi
done

NODE_VERSION=$(node --version | sed 's/^v//')
NODE_MAJOR=$(printf '%s\n' "$NODE_VERSION" | cut -d. -f1)
NODE_MINOR=$(printf '%s\n' "$NODE_VERSION" | cut -d. -f2)
if [ "$NODE_MAJOR" -lt 22 ] || { [ "$NODE_MAJOR" -eq 22 ] && [ "$NODE_MINOR" -lt 12 ]; }; then
  printf 'Aria requires Node.js 22.12 or later (found %s).\n' "$NODE_VERSION" >&2
  exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PYTHON_MAJOR=$(printf '%s\n' "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(printf '%s\n' "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; }; then
  printf 'Aria requires Python 3.11 or later (found %s).\n' "$PYTHON_VERSION" >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
npm ci

ARIA_PYTHON="$SCRIPT_DIR/.venv/bin/python" npm start
