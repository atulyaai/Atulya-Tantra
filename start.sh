#!/usr/bin/env bash
# Atulya — start here on Linux/macOS. The counterpart to start.bat:
# same four steps, same messages, no Windows-only pieces.
set -u

cd "$(dirname "$0")" || exit 1
export PYTHONDONTWRITEBYTECODE=1

printf '\n  +------------------------------------------+\n'
printf '  |                  ATULYA                  |\n'
printf '  |   Digital Organism OS                    |\n'
printf '  +------------------------------------------+\n\n'

# ---------------------------------------------------------------- 1. python
echo "  [1/4] Checking Python environment..."
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
    if command -v python3 >/dev/null 2>&1; then PYTHON=python3
    elif command -v python >/dev/null 2>&1; then PYTHON=python
    else
        echo "  ERROR: Python 3.10+ not found. Install it from python.org or your package manager."
        exit 1
    fi
fi
if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "  ERROR: $("$PYTHON" --version 2>&1) is too old. Atulya needs Python 3.10+."
    exit 1
fi

# ------------------------------------------------------- 2. read .env by hand
# Sourcing .env would run it as shell code; these are plain KEY=VALUE pairs and
# may contain spaces or $(...). Read them instead, and drop CRs because .env is
# often edited on Windows.
if [ -f .env ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        line=${line%$'\r'}
        case "$line" in ''|\#*) continue ;; esac
        key=${line%%=*}
        val=${line#*=}
        case "$val" in
            \"*\") val=${val#\"}; val=${val%\"} ;;
            \'*\') val=${val#\'}; val=${val%\'} ;;
        esac
        [ -n "$key" ] && export "$key=$val"
    done < .env
fi
: "${ATULYA_HOST:=127.0.0.1}"
: "${ATULYA_PORT:=8501}"

echo "  [2/4] Checking Python dependencies..."
if ! "$PYTHON" -c 'import fastapi, uvicorn' 2>/dev/null; then
    echo "  Installing Atulya — first run only..."
    "$PYTHON" -m pip install -q -e ".[voice]" || \
        echo "  WARNING: some packages failed to install. Run: $PYTHON -m pip install -e '.[voice]'"
fi

# Local brain. On Windows start.bat installs a ready-made llama-cpp-python
# wheel; on Linux that package compiles from source, which needs gcc and takes
# minutes, so we only report whether it is present. install.py --profile full
# is the place that installs it.
if [ "${ATULYA_AUTO_DOWNLOAD_MODEL:-true}" = "false" ]; then
    echo "  Local brain skipped - using the cloud brain from .env."
elif "$PYTHON" -c 'import llama_cpp' 2>/dev/null; then
    echo "  Local brain: available"
else
    echo "  Local brain: not installed (optional). Install with: $PYTHON -m pip install -e '.[brain]'"
fi

# ------------------------------------------------------------- 3. web UI build
echo "  [3/4] Building the web app..."
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    "$PYTHON" webui/build.py || echo "  WARNING: the web app failed to build, so there is no web UI."
    [ -f webui/dist/index.html ] || echo "  WARNING: webui/dist/index.html is missing."
else
    if [ -f webui/dist/index.html ]; then
        echo "  Node.js not found - using the existing build, which may be out of date."
    else
        echo "  WARNING: Node.js not found and there is no existing build. Install Node.js 18+."
    fi
    echo "  Note: Node.js is also required by the MCP tool servers (filesystem, git, playwright, fetch)."
fi

# ----------------------------------------------------------------- 4. run it
if [ "${ATULYA_HTTPS:-}" = "on" ]; then SCHEME=https; else SCHEME=http; fi
SHOW_HOST=$ATULYA_HOST
[ "$SHOW_HOST" = "0.0.0.0" ] && SHOW_HOST=YOUR_PC_IP

echo "  [4/4] Starting Atulya backend..."
echo ""
echo "  +------------------------------------------+"
echo "  |  Atulya is starting...                   |"
echo "  |                                          |"
echo "  |  Open:     $SCHEME://$SHOW_HOST:$ATULYA_PORT"
echo "  |                                          |"
echo "  |  Mobile: Set ATULYA_HOST=0.0.0.0 in .env |"
echo "  |          then open on your phone.        |"
echo "  |                                          |"
echo "  |  Ctrl+C to stop                          |"
echo "  +------------------------------------------+"
echo ""

exec "$PYTHON" -m atulya.server
