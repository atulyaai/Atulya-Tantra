#!/usr/bin/env bash
#
# Atulya Tantra — one command on Linux.
#
#     bash install.sh              ask for what is missing, set everything up
#     bash install.sh --yes        unattended: take every default
#     bash install.sh --check      report only, change nothing
#
# Stages, in the only order that can actually work:
#
#   1. the software Atulya runs on. This has to be a shell script: install.py
#      cannot install Python, because by the time it runs, Python is already
#      there or it is not.
#   2. the code, cloned into Atulya-Tantra/
#   3. your settings, asked one at a time and written to .env
#   4. a virtual environment, the packages, the dashboard build
#   5. a check that it really serves
#
# Re-running is safe: nothing already in .env is overwritten. No secret is ever
# printed — a value you have set shows only as "set".
set -euo pipefail

REPO_URL="${ATULYA_REPO:-https://github.com/atulyaai/Atulya-Tantra.git}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
UNATTENDED=0
CHECK_ONLY=0

for arg in "$@"; do
    case "$arg" in
        --yes|-y) UNATTENDED=1 ;;
        --check|--doctor) CHECK_ONLY=1 ;;
        -h|--help)
            sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "unknown option: $arg (try --help)"; exit 2 ;;
    esac
done

# ── output ───────────────────────────────────────────────────────────────────
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BOLD=$'\033[1m'; GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
    BOLD=''; GREEN=''; RED=''; YELLOW=''; DIM=''; RESET=''
fi

say()  { printf '%s\n' "$*"; }
stage() { printf '\n%s== %s ==%s\n' "$BOLD$CYAN" "$1" "$RESET"; }
CYAN=$'\033[36m'
ok()   { printf '  %sok%s    %s\n' "$GREEN" "$RESET" "$1"; }
warn() { printf '  %snote%s  %s\n' "$YELLOW" "$RESET" "$1"; }
bad()  { printf '  %sfail%s  %s\n' "$RED" "$RESET" "$1"; }
hint() { printf '        %s%s%s\n' "$DIM" "$1" "$RESET"; }

die() { bad "$1"; exit 1; }

# Root, or sudo when a password is available. -n never hangs on a prompt.
as_root() {
    if [ "$(id -u)" -eq 0 ]; then "$@"
    elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then sudo "$@"
    else return 1
    fi
}

# ── stage 1: the software ────────────────────────────────────────────────────
PKG_MGR=""
detect_pkg_mgr() {
    for m in apt-get dnf yum pacman zypper; do
        if command -v "$m" >/dev/null 2>&1; then PKG_MGR="$m"; return 0; fi
    done
    return 1
}

pkg_install() {   # pkg_install pkg1 pkg2 ...
    case "$PKG_MGR" in
        apt-get) as_root apt-get update -qq && as_root DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@" ;;
        dnf)     as_root dnf install -y -q "$@" ;;
        yum)     as_root yum install -y -q "$@" ;;
        pacman)  as_root pacman -S --noconfirm --needed "$@" ;;
        zypper)  as_root zypper --non-interactive install -q "$@" ;;
        *)       return 1 ;;
    esac
}

# Map what we need onto this distribution's names. Debian/Ubuntu is the case
# that bites: ensurepip lives in python3-venv, and without it `python -m venv`
# fails with "ensurepip is not available".
pkg_names_for() {
    case "$PKG_MGR" in
        apt-get) echo "$*" ;;
        pacman)  echo "$*" | sed -e 's/python3/python/' -e 's/python3-pip/python-pip/' -e 's/^nodejs$/nodejs/' ;;
        *)       echo "$*" ;;
    esac
}

# Vite's own gate: it refuses to run below 20.19/22.12 and says so. Ubuntu 24.04
# ships 18 through apt, so a check for mere presence reports a healthy install
# and the build still dies with "CustomEvent is not defined". Checking that a
# tool exists and checking that it works are two different questions.
node_version_ok() {
    local v major minor
    v="$(node --version 2>/dev/null | sed 's/^v//')" || return 1
    [ -n "$v" ] || return 1
    major="${v%%.*}"
    minor="${v#*.}"
    minor="${minor%%.*}"
    case "$major" in ''|*[!0-9]*) return 1 ;; esac
    case "$minor" in ''|*[!0-9]*) return 1 ;; esac
    [ "$major" -ge 23 ] && return 0
    { [ "$major" -eq 22 ] && [ "$minor" -ge 12 ]; } && return 0
    { [ "$major" -eq 20 ] && [ "$minor" -ge 19 ]; } && return 0
    return 1
}

# apt cannot take Debian or Ubuntu past 18. NodeSource can, and it is the
# upstream-recommended way on a box like this. It only runs on apt: every other
# package manager above already carries a current Node.
install_node_22() {
    detect_pkg_mgr || return 1
    [ "$PKG_MGR" = "apt-get" ] || return 1
    pkg_install curl ca-certificates gnupg >/dev/null 2>&1 || true
    local setup=/tmp/nodesource_setup.sh
    curl -fsSL https://deb.nodesource.com/setup_22.x -o "$setup" 2>/dev/null || return 1
    as_root bash "$setup" >/dev/null 2>&1 || { rm -f "$setup"; return 1; }
    as_root apt-get install -y -qq nodejs >/dev/null 2>&1 || { rm -f "$setup"; return 1; }
    rm -f "$setup"
    node_version_ok
}

stage_software() {
    say "  checking what this machine already has"

    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 missing — installing it"
        detect_pkg_mgr || die "no supported package manager (apt/dnf/yum/pacman/zypper); install Python 3.10+ yourself"
        pkg_install $(pkg_names_for python3 python3-venv python3-pip) || die "could not install python3"
    fi

    local pyver
    pyver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo 0.0)"
    case "$pyver" in
        3.1[0-9]|3.[2-9]*) ok "python3 $pyver" ;;
        *) die "python3 $pyver is too old — Atulya needs 3.10+ (install from python.org or your package manager)" ;;
    esac

    # The one that caught us on a fresh Ubuntu: venv/ensurepip split out.
    if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
        warn "ensurepip missing — the virtualenv step would fail"
        detect_pkg_mgr || die "install python3-venv for your distribution, then re-run"
        case "$PKG_MGR" in
            apt-get) pkg_install python3-venv python3-pip || die "could not install python3-venv" ;;
            *)       pkg_install python3-venv python3-pip 2>/dev/null || die "install python3-venv, then re-run" ;;
        esac
        python3 -c 'import ensurepip' >/dev/null 2>&1 || die "python3-venv installed but ensurepip still missing"
        ok "python3-venv installed"
    else
        ok "venv available"
    fi

    if ! command -v git >/dev/null 2>&1; then
        warn "git missing — installing it"
        detect_pkg_mgr || die "install git yourself, then re-run"
        pkg_install git || die "could not install git"
    fi
    ok "git $(git --version | awk '{print $3}')"

    # Node serves two different jobs, so it gets checked twice for two reasons.
    # The MCP tool servers (filesystem, git, playwright, fetch) shell out to npx
    # and run on almost anything. The web UI is built with Vite, which will not
    # start below 20.19/22.12 — so a node that is merely present reports a
    # healthy setup and still fails at the build.
    if node_version_ok; then
        ok "node $(node --version) + npm $(npm --version 2>/dev/null || echo '?')"
    else
        if command -v node >/dev/null 2>&1; then
            warn "node $(node --version 2>/dev/null) is too old for Vite (which needs 20.19+ or 22.12+)"
            hint "apt on Debian/Ubuntu only offers 18: the tool servers would work, the web UI would not"
        else
            warn "node/npm missing — installing it (needed by the tool servers and the dashboard build)"
            detect_pkg_mgr && pkg_install nodejs npm >/dev/null 2>&1 || true
        fi
        if node_version_ok; then
            ok "node $(node --version) + npm $(npm --version 2>/dev/null || echo '?')"
        elif install_node_22; then
            ok "node $(node --version) installed from NodeSource (apt only carries 18)"
        else
            bad "no Node.js the dashboard can be built with"
            hint "the four MCP tool servers still run — they only need some node"
            hint "but frontend/dist cannot be rebuilt, so whatever dist exists is what serves"
            hint "install Node 20.19+ from nodejs.org, then re-run this script"
        fi
    fi
}

# ── stage 2: the code ────────────────────────────────────────────────────────
DEST="$SCRIPT_DIR"

stage_code() {
    # Running from inside a checkout: use it rather than fetching a second copy.
    if [ -f "$SCRIPT_DIR/atulya/sevak.py" ] && [ -d "$SCRIPT_DIR/.git" ]; then
        DEST="$SCRIPT_DIR"
        ok "using the code next to this script ($DEST)"
        return 0
    fi

    DEST="${ATULYA_DIR:-$HOME/Atulya-Tantra}"
    if [ -d "$DEST/.git" ]; then
        ok "already cloned — updating"
        git -C "$DEST" pull --ff-only --quiet || warn "could not fast-forward; keeping what is there"
    else
        say "  cloning $REPO_URL"
        mkdir -p "$(dirname "$DEST")"
        git clone --depth 1 "$REPO_URL" "$DEST" || die "clone failed"
        ok "cloned into $DEST"
    fi
    cd "$DEST"
    DEST="$PWD"
    ok "working tree: $(git rev-parse --short HEAD 2>/dev/null || echo '?')"
}

# ── .env helpers ─────────────────────────────────────────────────────────────
# Read-only view of what is already set. Values are never printed.
env_has() { [ -f "$DEST/.env" ] && grep -q "^$1=" "$DEST/.env"; }

env_set() {   # env_set KEY VALUE — VALUE "" means leave it alone
    local key="$1" value="${2:-}" tmp line found=0
    [ -n "$value" ] || return 0
    touch "$DEST/.env"
    tmp="$(mktemp)"
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"          # .env edited on Windows carries CRs
        case "$line" in
            "$key"=*)
                found=1
                printf '%s=%s\n' "$key" "$value" ;;
            *) printf '%s\n' "$line" ;;
        esac
    done < "$DEST/.env" > "$tmp"
    [ "$found" -eq 1 ] || printf '%s=%s\n' "$key" "$value" >> "$tmp"
    mv "$tmp" "$DEST/.env"
}

shown() {     # never a value, only whether it exists
    if env_has "$1"; then printf 'set (%s)' "$(grep "^$1=" "$DEST/.env" | head -1 | cut -d= -f2- | tail -c 5 | tr -d '\r\n')"; else printf 'not set'; fi
}

ask_value() {  # ask_value KEY "label" "prompt" "default" [validator]
    local key="$1" label="$2" prompt="$3" def="${4:-}" validator="${5:-}" cur='' value=''
    if env_has "$key"; then
        cur="$(grep "^$key=" "$DEST/.env" | head -1 | cut -d= -f2- | tr -d '\r\n')"
        printf '  %s%-46s %sok%s    %s\n' "$label" "" "$GREEN" "$RESET" "$(shown "$key")"
        return 0
    fi
    printf '  %s%-46s %smissing%s\n' "$label" "" "$YELLOW" "$RESET"
    if [ "$UNATTENDED" -eq 1 ] || [ ! -t 0 ]; then
        [ -n "$def" ] && env_set "$key" "$def" && hint "defaulted: $key"
        return 0
    fi
    while true; do
        if [ -n "$def" ]; then printf '      %s [%s]: ' "$prompt" "$def"; else printf '      %s: ' "$prompt"; fi
        IFS= read -r value || value=""
        value="${value:-$def}"
        if [ -z "$value" ]; then
            hint "skipped — add $key to .env later"
            return 0
        fi
        if [ -n "$validator" ] && ! "$validator" "$value"; then
            continue
        fi
        break
    done
    env_set "$key" "$value"
    printf '  %sok%s    %s saved\n' "$GREEN" "$RESET" "$label"
}

is_bot_token()    { printf '%s' "$1" | grep -Eq '^[0-9]{6,12}:[A-Za-z0-9_-]{30,}$' || { say "      that does not look like a Telegram bot token (digits:letters)"; return 1; }; }
is_chat_id()      { printf '%s' "$1" | grep -Eq '^-?[0-9]{4,20}$' || { say "      a Telegram user id is a number like 123456789"; return 1; }; }
is_http_url()     { case "$1" in http://*|https://*) return 0 ;; *) say "      start with http:// or https://"; return 1 ;; esac; }
is_port()         { printf '%s' "$1" | grep -Eq '^[0-9]{2,5}$' || { say "      a port is a number like 8501"; return 1; }; }

make_token() {   # 32 URL-safe bytes, from the kernel's own entropy
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -base64 32 | tr '+/' '-_'
    else
        head -c 32 /dev/urandom | base64 | tr '+/' '-_'
    fi
}

# ── stage 3: settings, one at a time ─────────────────────────────────────────
stage_settings() {
    cd "$DEST"
    touch .env

    say ""
    say "  ${BOLD}Your settings.${RESET} Press Enter to skip anything optional."
    say "  ${DIM}Nothing already in .env is changed. Values are never printed back.${RESET}"
    say ""

    # The dashboard token guards the admin API, so it is always present.
    if ! env_has ATULYA_DASHBOARD_TOKEN; then
        env_set ATULYA_DASHBOARD_TOKEN "$(make_token)"
        printf '  %-46s %sok%s    generated (kept only in .env)\n' "Dashboard sign-in token" "$GREEN" "$RESET"
    else
        printf '  %-46s %sok%s    %s\n' "Dashboard sign-in token" "$GREEN" "$RESET" "$(shown ATULYA_DASHBOARD_TOKEN)"
    fi

    ask_value ATULYA_TELEGRAM_BOT_TOKEN "Telegram bot token" "token from @BotFather (blank to skip)" "" is_bot_token
    ask_value ATULYA_TELEGRAM_ALLOWLIST "Telegram user allowed to talk to Atulya" "your numeric Telegram id (blank to skip)" "" is_chat_id
    ask_value ATULYA_PUBLIC_URL "Public HTTPS address (Telegram /app)" "for example https://atulya.example.com (blank to skip)" "" is_http_url

    say ""
    say "  ${BOLD}A brain.${RESET} Atulya asks the first one that is set."
    say "  ${DIM}Free keys: openrouter.ai/keys, aistudio.google.com/app/apikey, console.groq.com/keys${RESET}"
    ask_value OPENROUTER_API_KEY "Brain key — OpenRouter" "OpenRouter key (blank to skip)" "" 'true'
    ask_value GEMINI_API_KEY     "Brain key — Google Gemini" "Gemini key (blank to skip)" "" 'true'
    ask_value GROQ_API_KEY       "Brain key — Groq" "Groq key (blank to skip)" "" 'true'
    ask_value DEEPSEEK_API_KEY   "Brain key — DeepSeek" "DeepSeek key (blank to skip)" "" 'true'

    # A valid model slug matters: a removed one 404s before any fallback runs.
    if ! env_has ATULYA_OPENROUTER_MODEL && env_has OPENROUTER_API_KEY; then
        env_set ATULYA_OPENROUTER_MODEL "google/gemma-4-31b-it:free,nvidia/nemotron-3-super-120b-a12b:free"
        hint "ATULYA_OPENROUTER_MODEL set to models that exist today"
    fi

    say ""
    ask_value ATULYA_HOST "Bind address" "127.0.0.1 private, 0.0.0.0 lets your phone reach it" "127.0.0.1"
    ask_value ATULYA_PORT "Port" "8501 unless something else uses it" "8501" is_port
    chmod 600 .env 2>/dev/null || true
    ok ".env written ($(grep -c '=' .env) settings, readable by you only)"
}

# ── stage 4: environment, packages, dashboard ────────────────────────────────
stage_build() {
    cd "$DEST"
    say "  creating the virtual environment"
    python3 -m venv .venv || die "could not create .venv"
    # shellcheck disable=SC1091
    . .venv/bin/activate

    say "  installing Atulya (first run only, this takes a minute)"
    python -m pip install --upgrade pip -q
    python -m pip install -e ".[serve]" -q || die "pip install failed"

    if command -v node >/dev/null 2>&1 && node_version_ok; then
        say "  building the dashboard"
        if python frontend/build.py > /tmp/atulya_dist_build.log 2>&1; then
            ok "dashboard built"
        else
            warn "dashboard build failed — whatever dist already exists is what serves"
            hint "reason: $(grep -v '^[[:space:]]*$' /tmp/atulya_dist_build.log | tail -1)"
            hint "run it yourself for the full trace:  cd frontend && npm run build"
        fi
    else
        if [ -f frontend/dist/index.html ]; then
            warn "no node — using the existing frontend/dist as-is"
        else
            bad "no node and no frontend/dist — there will be no web UI"
        fi
    fi
    ok "packages installed into .venv"
}

# ── stage 5: check ───────────────────────────────────────────────────────────
stage_check() {
    cd "$DEST"
    # shellcheck disable=SC1091
    [ -f .venv/bin/activate ] && . .venv/bin/activate
    say "  running the health check"
    if python install.py --doctor; then
        ok "ready"
    else
        warn "the items marked above still need attention"
    fi
}

# ── report ───────────────────────────────────────────────────────────────────
report_only() {
    say ""
    say "  ${BOLD}ATULYA TANTRA — check${RESET}"
    say ""
    say "  python3      $(command -v python3 >/dev/null 2>&1 && python3 --version 2>&1 || echo missing)"
    say "  git          $(command -v git >/dev/null 2>&1 && git --version 2>&1 || echo missing)"
    say "  node/npm     $(command -v node >/dev/null 2>&1 && node --version || echo 'missing — tool servers will not start')"
    say "  code         $([ -f "$SCRIPT_DIR/atulya/sevak.py" ] && echo "here ($SCRIPT_DIR)" || echo "not cloned yet")"
    if [ -f "$SCRIPT_DIR/.env" ]; then
        say "  .env         $(grep -c '=' "$SCRIPT_DIR/.env") settings"
    else
        say "  .env         not written yet"
    fi
    say "  .venv        $([ -d "$SCRIPT_DIR/.venv" ] && echo present || echo 'not created yet')"
    say "  dist         $([ -f "$SCRIPT_DIR/frontend/dist/index.html" ] && echo built || echo 'not built yet')"
    say ""
    say "  ${DIM}Run 'bash install.sh' to do it. This changed nothing.${RESET}"
}

# ── main ─────────────────────────────────────────────────────────────────────
if [ "$CHECK_ONLY" -eq 1 ]; then
    report_only
    exit 0
fi

printf '\n%s  ATULYA TANTRA — setup%s\n' "$BOLD" "$RESET"
say "  ${DIM}software, then the code, then your settings — one command, Linux.$RESET"

stage "1/5 Software"
stage_software

stage "2/5 Code"
stage_code

stage "3/5 Settings"
stage_settings

stage "4/5 Environment"
stage_build

stage "5/5 Check"
stage_check

say ""
say "  ${GREEN}${BOLD}Done.${RESET} Start Atulya with:"
say ""
say "      cd $DEST"
say "      ${BOLD}. .venv/bin/activate && python -m atulya.sevak${RESET}"
say ""
say "  ${DIM}Make it start by itself:  python install.py --service   (systemd, at boot)${RESET}"
say "  ${DIM}Same thing, in a terminal: ./start.sh${RESET}"
say ""
