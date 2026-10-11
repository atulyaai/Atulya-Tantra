#!/usr/bin/env bash
set -eu
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if command -v python3 >/dev/null 2>&1; then
    ATULYA_PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
    ATULYA_PYTHON_BIN=python
elif [ ! -x .venv/bin/python ]; then
    echo "Python was not found; installing a private copy with uv..."
    exec sh "$ROOT/install.sh"
else
    ATULYA_PYTHON_BIN=.venv/bin/python
fi
ATULYA_VENV_DIR=.venv
if [ -x .venv/bin/python ] && [ -f .venv/pyvenv.cfg ]; then
    if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
        echo "Repairing Atulya's local Python environment..."
        "$ATULYA_PYTHON_BIN" -m venv --upgrade .venv
    fi
else
    echo "Creating Atulya's local Python environment..."
    "$ATULYA_PYTHON_BIN" -m venv "$ATULYA_VENV_DIR"
fi
"$ATULYA_VENV_DIR/bin/python" tools/bootstrap.py
exec "$ATULYA_VENV_DIR/bin/python" -m atulya.cli serve

