#!/usr/bin/env sh
# Atulya installer for Linux and macOS (x86-64 and ARM64). No root needed.
#
#   curl -fsSL https://raw.githubusercontent.com/atulyaai/Atulya-Tantra/main/install.sh | sh
#   sh install.sh --service          # also start Atulya automatically at login
#   sh install.sh --remove-service   # stop and remove the login service (keeps data)
#
# Steps: get the code (git, or a tarball when git is missing), install uv and a
# private Python 3.12 if no Python >= 3.10 exists, create .venv, run setup.
set -eu

REPO="https://github.com/atulyaai/Atulya-Tantra"
DIR="${ATULYA_DIR:-$HOME/Atulya-Tantra}"
SERVICE=0
REMOVE=0
for arg in "$@"; do
    case "$arg" in
        --service) SERVICE=1 ;;
        --remove-service) REMOVE=1 ;;
        --dir=*) DIR="${arg#--dir=}" ;;
        *) echo "Unknown option: $arg"; exit 2 ;;
    esac
done

say() { printf '\033[36m==>\033[0m %s\n' "$*"; }
OS="$(uname -s)"
LABEL="ai.atulya.host"

remove_service() {
    if [ "$OS" = "Darwin" ]; then
        PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
        launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
        rm -f "$PLIST"
    else
        systemctl --user disable --now atulya.service 2>/dev/null || true
        rm -f "$HOME/.config/systemd/user/atulya.service"
        systemctl --user daemon-reload 2>/dev/null || true
    fi
    say "Login service removed. Project files and personal data were kept."
}

if [ "$REMOVE" = 1 ]; then remove_service; exit 0; fi

# 1. Code: use this checkout when run from inside it, otherwise clone/download.
if [ -f "./pyproject.toml" ] && grep -q 'name = "atulya' ./pyproject.toml 2>/dev/null; then
    DIR="$(pwd)"
elif [ -d "$DIR/.git" ] && command -v git >/dev/null 2>&1; then
    say "Updating $DIR"; git -C "$DIR" pull --ff-only
elif [ ! -f "$DIR/pyproject.toml" ]; then
    say "Downloading Atulya into $DIR"
    if command -v git >/dev/null 2>&1; then
        git clone --depth 1 "$REPO.git" "$DIR"
    else
        mkdir -p "$DIR"
        curl -fsSL "$REPO/archive/refs/heads/main.tar.gz" | tar -xz --strip-components=1 -C "$DIR"
    fi
fi
cd "$DIR"

# 2. Python: reuse a system Python >= 3.10, else a uv-managed private one.
PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys, venv; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then
        PY="$candidate"; break
    fi
done
if [ ! -x .venv/bin/python ]; then
    if [ -n "$PY" ]; then
        say "Creating .venv with $($PY --version)"
        "$PY" -m venv .venv || PY=""
    fi
    if [ -z "$PY" ] || [ ! -x .venv/bin/python ]; then
        if ! command -v uv >/dev/null 2>&1; then
            say "Installing uv (user-local Python manager)"
            curl -LsSf https://astral.sh/uv/install.sh | sh
            PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        fi
        say "Creating .venv with a private Python 3.12"
        rm -rf .venv
        uv venv --seed --python 3.12 .venv
    fi
fi

# 3. Config and setup (packages + models sized to this machine).
[ -f .env ] || cp .env.example .env
say "Installing packages and preparing models (first run downloads a few GB)"
.venv/bin/python tools/bootstrap.py

# 4. Optional login service.
if [ "$SERVICE" = 1 ]; then
    if [ "$OS" = "Darwin" ]; then
        PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
        mkdir -p "$HOME/Library/LaunchAgents" data/logs
        cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$DIR/.venv/bin/python</string><string>-m</string><string>atulya.cli</string><string>pc-host</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>30</integer>
</dict></plist>
EOF
        launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
        launchctl bootstrap "gui/$(id -u)" "$PLIST"
    else
        mkdir -p "$HOME/.config/systemd/user"
        cat > "$HOME/.config/systemd/user/atulya.service" <<EOF
[Unit]
Description=Atulya assistant (loopback only)
After=network-online.target

[Service]
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python -m atulya.cli pc-host
Restart=on-failure
RestartSec=10
StartLimitBurst=5

[Install]
WantedBy=default.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable --now atulya.service
        say "Tip: 'loginctl enable-linger $USER' keeps it running when you are logged out."
    fi
    say "Atulya starts automatically at login. Logs: $DIR/data/logs/pc-host.log"
    say "Open http://localhost:8501"
else
    say "Starting Atulya at http://localhost:8501 (Ctrl+C to stop)"
    exec .venv/bin/python -m atulya.cli serve
fi
