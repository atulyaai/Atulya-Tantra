#!/usr/bin/env python3
"""Atulya Tantra — one-command installer, configurator and health check.

    python install.py            # interactive: shows what is already set,
                                 # asks only for what is missing, then starts
    python install.py --doctor   # report only, change nothing
    python install.py --yes      # unattended (cPanel, CI, VPS provisioning)

Nothing secret is ever printed: keys are shown as "set (last 4)" only.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import secrets
import shutil
import subprocess
import sys
import urllib.error
from urllib.parse import urlsplit
import urllib.request
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

IS_WINDOWS = os.name == "nt"
# Debian/Ubuntu ship ensurepip in a separate package, so on a fresh box
# `python -m ensurepip` fails with "ensurepip is not available" and the fix is
# apt, not Python. Detected rather than guessed so the advice is correct.
IS_DEBIAN = Path("/etc/debian_version").exists()
PIP_FIX = "sudo apt install python3-venv python3-pip" if IS_DEBIAN else "python -m ensurepip --upgrade"
GREEN, RED, YELLOW, CYAN, DIM, BOLD, RESET = (
    "\033[32m",
    "\033[31m",
    "\033[33m",
    "\033[36m",
    "\033[2m",
    "\033[1m",
    "\033[0m",
)
if not sys.stdout.isatty() or IS_WINDOWS:
    GREEN = RED = YELLOW = CYAN = DIM = BOLD = RESET = ""  # plain output when piped

OK, BAD, WARN = f"{GREEN}ok{RESET}", f"{RED}missing{RESET}", f"{YELLOW}note{RESET}"


def say(line: str = "") -> None:
    print(line, flush=True)


def _fix_console() -> None:
    """Windows consoles default to cp1252 and mangle UTF-8 box/dash characters."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


def step(title: str) -> None:
    say(f"\n{BOLD}{CYAN}== {title}{RESET}")


_fix_console()


# ── configuration model ──────────────────────────────────────────────────────
class Item:
    """One .env setting: what it is, whether it is set, and how to get it."""

    def __init__(
        self,
        key: str,
        label: str,
        *,
        secret: bool = False,
        ask: str | None = None,
        hint: str = "",
        validate: Callable[[str], str | None] | None = None,
        generate: Callable[[], str] | None = None,
        default: str = "",
    ) -> None:
        self.key, self.label, self.secret, self.ask = key, label, secret, ask
        self.hint, self.validate, self.generate, self.default = hint, validate, generate, default

    def raw(self) -> str:
        return (os.environ.get(self.key) or "").strip()

    def is_set(self) -> bool:
        return bool(self.raw())

    def shown(self) -> str:
        value = self.raw()
        if not value:
            return ""
        if self.secret:
            return f"set ({value[-4:]})" if len(value) > 4 else "set"
        return f"set ({value})"


_BOT_TOKEN = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")


def _bot_token(value: str) -> str | None:
    return None if _BOT_TOKEN.match(value) else "That does not look like a Telegram bot token (digits:letters)."


def _chat_id(value: str) -> str | None:
    return None if re.fullmatch(r"-?\d{4,20}", value) else "A Telegram user id is a number like 1484854122."


def _http_url(value: str) -> str | None:
    return None if value.startswith(("http://", "https://")) else "Start with http:// or https://."


def _https_origin(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and parsed.hostname and parsed.path in {"", "/"}
                 and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment)
        parsed.port  # validate a supplied port
    except ValueError:
        valid = False
    return None if valid else "Use a public HTTPS address such as https://atulya.example.com (no path)."


ITEMS: list[Item] = [
    Item(
        "ATULYA_DASHBOARD_TOKEN",
        "Dashboard sign-in token",
        secret=True,
        generate=lambda: secrets.token_urlsafe(32),
        hint="generated for you if you do not have one",
    ),
    Item(
        "ATULYA_TELEGRAM_BOT_TOKEN",
        "Telegram bot token",
        secret=True,
        ask="Telegram bot token (from @BotFather, blank to skip)",
        hint="open Telegram, message @BotFather, send /newbot, paste the token it gives you",
        validate=_bot_token,
    ),
    Item(
        "ATULYA_TELEGRAM_ALLOWLIST",
        "Telegram user allowed to talk to Atulya",
        ask="Your Telegram numeric user id (blank to skip)",
        hint="message @userinfobot in Telegram — it replies with your id",
        validate=_chat_id,
    ),
    Item(
        "ATULYA_PUBLIC_URL",
        "Public HTTPS address for the Telegram Mini App",
        ask="Public HTTPS URL for this Atulya server (blank to skip)\n  Set up BotFather /newapp and a public HTTPS tunnel first",
        hint="for example https://your-domain.example — needed for Telegram /app and its menu button",
        validate=_https_origin,
    ),
    Item(
        "OPENROUTER_API_KEY",
        "Brain key — OpenRouter (300+ models, free ones included)",
        secret=True,
        ask="OpenRouter key (blank to skip)",
        validate=lambda v: None,
        hint="sign up at openrouter.ai/keys — free tier works",
    ),
    Item(
        "GEMINI_API_KEY",
        "Brain key — Google Gemini (free tier)",
        secret=True,
        ask="Gemini key (blank to skip)",
        hint="aistudio.google.com/app/apikey",
    ),
    Item(
        "GROQ_API_KEY",
        "Brain key — Groq (fastest free tier)",
        secret=True,
        ask="Groq key (blank to skip)",
        hint="console.groq.com/keys",
    ),
    Item(
        "DEEPSEEK_API_KEY",
        "Brain key — DeepSeek (very cheap)",
        secret=True,
        ask="DeepSeek key (blank to skip)",
        hint="platform.deepseek.com/api_keys",
    ),
    Item(
        "ATULYA_BRIEFING_AT",
        "Morning briefing time",
        default="",
        ask="Morning briefing time as HH:MM (blank to skip)",
        hint="for example 08:00",
        validate=lambda v: (
            None
            if (not v or re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", v))
            else "Use 24-hour HH:MM, e.g. 08:00 or 21:30."
        ),
    ),
    Item(
        "ATULYA_HOST",
        "Bind address",
        default="127.0.0.1",
        hint="127.0.0.1 keeps it private; 0.0.0.0 lets your phone reach it",
    ),
    Item("ATULYA_PORT", "Port", default="8501", hint="8501 unless something else uses it"),
]

PROFILE_EXTRAS = {
    "basic": "serve",
    "voice": "serve,voice",
    "full": "serve,voice,control,ambient,brain",
    "server": "serve,brain",
}


# ── environment reading ──────────────────────────────────────────────────────
def load_existing() -> None:
    """Merge .env into os.environ without overriding anything already exported."""
    from atulya.adhar import load_env

    try:
        load_env([ROOT / ".env"])
    except Exception:
        pass


# ── preflight ────────────────────────────────────────────────────────────────
def preflight() -> list[tuple[str, bool, str, str]]:
    checks: list[tuple[str, bool, str, str]] = []
    py = sys.version_info
    checks.append(
        ("Python 3.10+", py >= (3, 10), f"{py.major}.{py.minor}.{py.micro}", "install python.org/downloads and re-run")
    )
    try:
        import pip  # noqa: F401

        checks.append(("pip", True, "available", ""))
    except Exception:
        checks.append(("pip", False, "missing", PIP_FIX))
    try:
        import fastapi  # noqa: F401

        checks.append(("Atulya package", True, "importable", ""))
    except Exception:
        checks.append(("Atulya package", False, "not installed", "pip install -e ."))
    node = shutil.which("node")
    npm = shutil.which("npm")
    if node and npm:
        try:
            nv = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=15).stdout.strip()
        except Exception:
            nv = "found"
        checks.append(("Node.js (tool servers, web UI)", True, nv, ""))
    else:
        checks.append(
            (
                "Node.js (tool servers, web UI)",
                False,
                "not found",
                # Still starts with "optional" because a server with a prebuilt
                # webui works without it - but the consequence is now stated,
                # because four MCP servers silently die without npx.
                "optional — but without it the MCP tool servers (filesystem, git, "
                "playwright, fetch) cannot start and the web UI cannot be built; "
                "install Node.js 18+ from nodejs.org or your package manager",
            )
        )
    return checks


# ── status table ─────────────────────────────────────────────────────────────
def status_table() -> tuple[int, int]:
    say(f"  {'Setting':44} {'State':16} How to get it")
    say(f"  {'-' * 44} {'-' * 16} {'-' * 44}")
    present = missing = 0
    for item in ITEMS:
        if item.is_set():
            present += 1
            say(f"  {item.label[:44]:44} {OK:16} {DIM}{item.shown()}{RESET}")
        else:
            missing += 1
            say(f"  {item.label[:44]:44} {BAD:16} {DIM}{item.hint}{RESET}")
    return present, missing


def brain_ready() -> bool:
    return any(
        Item(k, "").is_set()
        for k in (
            "OPENROUTER_API_KEY",
            "GEMINI_API_KEY",
            "GROQ_API_KEY",
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "ATULYA_OLLAMA_MODEL",
        )
    )


def _summary(present: int, missing: int) -> str:
    """The one line printed under the status table."""
    if missing:
        return f"\n  {present} set, {missing} missing. {YELLOW}Nothing above prints a secret.{RESET}"
    return f"\n  All {present} settings are already configured."


# ── interview ────────────────────────────────────────────────────────────────
def ask(prompt: str, default: str = "") -> str:
    try:
        suffix = f" [{default}]" if default else ""
        answer = input(f"  {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        say("")
        return default
    return answer or default


def interview(quiet: bool) -> list[str]:
    """Ask for the missing settings only. Returns the keys that changed."""
    from atulya.adhar import set_env_value

    changed: list[str] = []
    # A missing dashboard token is a security hole, so it is always created.
    token = next(i for i in ITEMS if i.key == "ATULYA_DASHBOARD_TOKEN")
    if not token.is_set():
        set_env_value(token.key, token.generate())
        changed.append(token.key)
        say(f"  {OK} {token.label}: generated (kept only in your .env)")

    wanted = [i for i in ITEMS if not i.is_set() and i.ask and i.key != "ATULYA_DASHBOARD_TOKEN"]
    if not wanted:
        return changed

    say(f"\n  {BOLD}{len(wanted)} setting(s) still needed.{RESET} Press Enter to skip anything optional.")
    for item in wanted:
        if quiet:
            if item.key == "ATULYA_BRIEFING_AT" and item.default:
                set_env_value(item.key, item.default)
                changed.append(item.key)
            continue
        value = ask(item.ask, item.default)
        if value and item.validate:
            while problem := item.validate(value):
                say(f"    {RED}{problem}{RESET}")
                value = ask(item.ask, item.default)
                if not value:
                    break
        if not value:
            say(f"    {DIM}skipped — you can add {item.key} to .env later{RESET}")
            continue
        set_env_value(item.key, value)
        changed.append(item.key)
        say(f"  {OK} {item.label} saved")
    return changed


# ── install ──────────────────────────────────────────────────────────────────
def pip_install(extras: str, quiet: bool) -> bool:
    target = f".[{extras}]" if extras else "."
    say(f"  pip install -e {target}")
    cmd = [sys.executable, "-m", "pip", "install", "-e", target]
    if quiet:
        cmd.append("-q")
    return subprocess.call(cmd, cwd=ROOT) == 0


def build_dashboard(quiet: bool) -> bool:
    if not (shutil.which("node") and shutil.which("npm")):
        say(
            f"  {WARN} Node.js not found — skipping the web UI build "
            f"({DIM}an existing frontend/dist is used as-is, and the MCP tool servers "
            f"filesystem/git/playwright/fetch will not start{RESET})"
        )
        return False
    say("  Checking and building the dashboard when its source has changed...")
    result = subprocess.call([sys.executable, str(ROOT / "frontend" / "build.py")], cwd=ROOT)
    if result != 0:
        say(f"  {RED}dashboard build failed{RESET}")
        return False
    say(f"  {OK} dashboard is current")
    return True


# ── self-repair ──────────────────────────────────────────────────────────────
# Every failure below used to print "-> run this yourself".  Most of them are
# just a command we can run here instead of making the human copy/paste it.
# Anything that needs a human (downloading Python, an API key from a website)
# is deliberately absent from this map and still gets printed as advice.
_SELF_FIX: dict[str, list[str]] = {
    "python -m ensurepip --upgrade": [sys.executable, "-m", "ensurepip", "--upgrade"],
    "pip install -e .": [sys.executable, "-m", "pip", "install", "-e", "."],
    "pip install -e '.[serve]'": [sys.executable, "-m", "pip", "install", "-e", ".[serve]"],
    "pip install -e '.[voice]'": [sys.executable, "-m", "pip", "install", "-e", ".[voice]"],
}
if IS_DEBIAN:
    # `sudo -n` never prompts: if a password is needed the repair exits at once
    # and the advice is printed, instead of hanging on a prompt we cannot answer.
    _SELF_FIX[PIP_FIX] = ["sudo", "-n", "apt", "install", "-y", "python3-venv", "python3-pip"]


def autofix(fix: str) -> bool:
    """Run a repair we can do ourselves. True when we actually attempted it."""
    cmd = _SELF_FIX.get(fix.strip())
    if not cmd:
        return False
    say(f"  {YELLOW}repairing:{RESET} {' '.join(cmd)}")
    try:
        done = subprocess.run(cmd, timeout=1800)
    except Exception as exc:  # noqa: BLE001 - report, never crash the installer
        say(f"  {RED}repair failed: {exc}{RESET}")
        return False
    if done.returncode != 0:
        say(f"  {RED}repair failed (exit {done.returncode}){RESET}")
        return False
    say(f"  {OK} repaired")
    return True


def preflight_repair() -> list[tuple[str, bool, str, str]]:
    """Preflight, running every command-backed fix first and re-checking after.

    A failure that repairs itself is no longer a failure, so the installer
    keeps going instead of stopping and asking the user to re-run it.
    """
    checks = preflight()
    if any(not ok for _, ok, _, _ in checks):
        for _, ok, _, fix in checks:
            if not ok and autofix(fix):
                pass
        checks = preflight()
    return checks


# ── doctor ───────────────────────────────────────────────────────────────────
def doctor() -> bool:
    """Real end-to-end checks. Returns True when Atulya is ready to serve."""
    from atulya.adhar import env_path

    failures = 0

    def line(label: str, ok: bool, detail: str = "", fix: str = "", state: str = "") -> None:
        nonlocal failures
        if not ok and state != "note" and autofix(fix):
            # The repair ran and exited cleanly; re-check before judging it.
            ok, detail = True, "repaired"
        if state == "note":
            mark, counted = f"{YELLOW}note{RESET}", False
        else:
            mark, counted = (OK if ok else BAD), (not ok)
        if counted:
            failures += 1
        say(f"  {label:34} {mark:16} {DIM}{detail}{RESET}")
        if counted and fix:
            say(f"      -> {YELLOW}{fix}{RESET}")

    say(f"  config file: {env_path()}")
    for label, ok, detail, fix in preflight():
        line(label, ok, detail, fix)

    # Four MCP servers shell out to npx. Reported here rather than only in
    # preflight because this is the report people actually read when a tool
    # mysteriously does nothing. A note, not a failure: a server with a
    # prebuilt webui and no tool servers is still a working server.
    node_here = bool(shutil.which("node") and shutil.which("npm"))
    line(
        "MCP tool servers (need Node)",
        node_here,
        "node found" if node_here else "filesystem, git, playwright and fetch will not start",
        "install Node.js 18+ from nodejs.org or your package manager",
        state="" if node_here else "note",
    )

    try:
        from atulya import mastishk  # noqa: F401

        line("brain module imports", True)
    except Exception as exc:
        line("brain module imports", False, str(exc)[:60], "pip install -e '.[serve]'")

    cloud_or_named_model = brain_ready()
    line(
        "at least one brain key",
        cloud_or_named_model,
        "configured" if cloud_or_named_model else "none; local fallback may be used",
        "add a cloud key for hosted brains, or install/configure a local model",
        state="" if cloud_or_named_model else "note",
    )
    line(
        "dashboard token",
        bool(os.environ.get("ATULYA_DASHBOARD_TOKEN")),
        next((i.shown() for i in ITEMS if i.key == "ATULYA_DASHBOARD_TOKEN"), ""),
        "python install.py (it generates one)",
    )
    telegram_ready = bool(os.environ.get("ATULYA_TELEGRAM_BOT_TOKEN")) and bool(
        os.environ.get("ATULYA_TELEGRAM_ALLOWLIST")
    )
    line(
        "Telegram bot",
        telegram_ready,
        "token + allowlist set" if telegram_ready else "optional",
        "add ATULYA_TELEGRAM_BOT_TOKEN and ATULYA_TELEGRAM_ALLOWLIST",
        state="" if telegram_ready else "note",
    )

    # Voice stack: import only, no model download.
    try:
        import edge_tts  # noqa: F401

        line("text-to-speech (edge-tts)", True)
    except Exception:
        line("text-to-speech (edge-tts)", False, "optional; local/system speech may still work",
             "pip install -e '.[voice]'", state="note")

    # Live server probe: only if something is already listening.
    port = os.environ.get("ATULYA_PORT", "8501")
    host = (
        "127.0.0.1"
        if os.environ.get("ATULYA_HOST", "127.0.0.1") == "0.0.0.0"
        else os.environ.get("ATULYA_HOST", "127.0.0.1")
    )
    url = f"http://{host}:{port}/api/health"
    # Probe with the dashboard token we hold. Sending no token made every healthy
    # server look like an anonymous 401, which is exactly how a server that
    # silently ignores ATULYA_DASHBOARD_TOKEN slips through.
    token = (os.environ.get("ATULYA_DASHBOARD_TOKEN") or "").strip()
    request = urllib.request.Request(url, headers={"X-Atulya-Token": token} if token else {})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            line("running server /api/health", response.status == 200, f"HTTP {response.status} at {url}")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403) and not token:
            line(
                "running server /api/health",
                True,
                f"HTTP {exc.code} at {url} — listening, needs a token",
                "",
                state="note",
            )
        elif exc.code in (401, 403):
            line(
                "running server /api/health",
                False,
                "the server rejected your ATULYA_DASHBOARD_TOKEN",
                "restart Atulya so it re-reads .env",
            )
        else:
            line("running server /api/health", False, f"HTTP {exc.code} at {url}", "")
    except Exception:
        say(f"  {'running server /api/health':34} {WARN:16} {DIM}not running (start it below){RESET}")

    return failures == 0


# ── service install ──────────────────────────────────────────────────────────
# "Make it work on its own" is the part a plain pip install never does. On
# Linux that is a systemd unit; on Windows there is no equivalent a script may
# create without elevation, so a shortcut in the sign-in Startup folder does it.
SERVICE_NAME = "atulya.service"


def _service_unit() -> str:
    """The unit runs the interpreter that ran the installer, so a venv sticks."""
    return f"""[Unit]
Description=Atulya Tantra assistant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={getpass.getuser()}
WorkingDirectory={ROOT}
ExecStart={sys.executable} -m atulya.sevak
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""


def _install_systemd_unit() -> bool:
    if not shutil.which("systemctl"):
        say(f"  {YELLOW}no systemctl here{RESET} (macOS, WSL or a container) — add the unit by hand:")
        say(f"  {DIM}see docs/DEPLOYMENT.md, then point ExecStart at {sys.executable}{RESET}")
        return False
    script = (
        f"tee /etc/systemd/system/{SERVICE_NAME} <<'ATEOF'\n"
        f"{_service_unit()}"
        "ATEOF\n"
        "systemctl daemon-reload\n"
        f"systemctl enable {SERVICE_NAME}\n"
    )
    say(f"  writing /etc/systemd/system/{SERVICE_NAME}")
    try:
        # -n: never prompt for a sudo password we cannot type into.
        done = subprocess.run(["sudo", "-n", "bash", "-s"], input=script, text=True, capture_output=True)
    except Exception as exc:  # noqa: BLE001 - report, never crash the installer
        say(f"  {RED}could not run sudo: {exc}{RESET}")
        return False
    if done.returncode != 0:
        say(f"  {RED}{(done.stderr or done.stdout).strip()[:200] or 'sudo failed'}{RESET}")
        say(f"  {YELLOW}run `sudo -v` first so sudo knows your password, then re-run this.{RESET}")
        return False
    say(f"  {OK} installed and enabled at boot")
    say(f"      start now:  {BOLD}sudo systemctl start {SERVICE_NAME}{RESET}")
    say(f"      is it up:   {BOLD}sudo systemctl status {SERVICE_NAME}{RESET}")
    return True


def _install_startup_shortcut() -> bool:
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        say(f"  {RED}APPDATA is not set, so the sign-in folder is unknown{RESET}")
        return False
    startup = Path(appdata) / "Microsoft/Windows/Start Menu/Programs/Startup"
    try:
        startup.mkdir(parents=True, exist_ok=True)
        # CRLF because cmd.exe reads this at every sign-in.
        (startup / "Atulya.bat").write_text(
            "@echo off\r\n"
            f'cd /d "{ROOT}"\r\n'
            f'start "" /min "{sys.executable}" -m atulya.sevak\r\n',
            encoding="utf-8",
        )
    except OSError as exc:
        say(f"  {RED}could not write the Startup folder: {exc}{RESET}")
        return False
    say(f"  {OK} starts by itself when you sign in to Windows")
    say(f"      {DIM}stop it starting: delete {startup / 'Atulya.bat'}{RESET}")
    return True


def install_service() -> bool:
    """--service: run Atulya without anyone opening a terminal."""
    say("  " + ("sign-in Startup shortcut" if IS_WINDOWS else "systemd unit"))
    return _install_startup_shortcut() if IS_WINDOWS else _install_systemd_unit()


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Install and configure Atulya Tantra")
    parser.add_argument("--doctor", action="store_true", help="report status only, change nothing")
    parser.add_argument("--yes", "-y", action="store_true", help="unattended: accept defaults, no prompts")
    parser.add_argument(
        "--profile", choices=sorted(PROFILE_EXTRAS), default="", help="which optional features to install"
    )
    parser.add_argument("--no-start", action="store_true", help="do not offer to start Atulya")
    parser.add_argument(
        "--service",
        action="store_true",
        help="also make Atulya start on its own (systemd unit on Linux, sign-in shortcut on Windows)",
    )
    args = parser.parse_args()

    say(f"\n{BOLD}  ATULYA TANTRA — setup{RESET}")

    load_existing()

    step("1. Preflight")
    bad = 0
    for label, ok, detail, fix in preflight_repair():
        say(f"  {label:34} {OK if ok else BAD:16} {DIM}{detail}{RESET}")
        if not ok and not fix.startswith("optional"):
            bad += 1
            say(f"      -> {YELLOW}{fix}{RESET}")
    if bad:
        say(f"\n{RED}Fix the required setup items listed above, then run the installer again.{RESET}")
        return 1

    if args.doctor:
        step("Status")
        status_table()
        step("2. Health check")
        return 0 if doctor() else 1

    step("2. What is already configured")
    present, missing = status_table()
    say(_summary(present, missing))

    step("3. Install features")
    profile = args.profile or ("full" if not args.yes else "basic")
    if not args.profile:
        if args.yes:
            say(f"  profile: {profile} (unattended)")
        else:
            say("  Which install do you want?")
            say("    1) basic   — server + dashboard only          (fastest)")
            say("    2) voice   — + spoken replies, transcription  (recommended)")
            say("    3) full    — + PC control, always-on listener  (the Jarvis setup)")
            say("    4) server  — headless, no voice (cPanel/VPS)")
            choice = ask("Choose 1-4", "2")
            profile = {"1": "basic", "2": "voice", "3": "full", "4": "server"}.get(choice.strip(), "voice")
    extras = PROFILE_EXTRAS[profile]
    if not pip_install(extras, args.yes):
        say(f"{RED}Package install failed — see the pip output above.{RESET}")
        return 1
    say(f"  {OK} installed extras: {extras}")

    step("4. Configure")
    interview(quiet=args.yes)
    # Profile-driven defaults for switches that are otherwise easy to forget.
    from atulya.adhar import set_env_value

    if profile == "full":
        set_env_value("ATULYA_PC_CONTROL", "on")
        set_env_value("ATULYA_AUTO_DOWNLOAD_MODEL", "true")
        if not os.environ.get("ATULYA_BRIEFING_AT"):
            set_env_value("ATULYA_BRIEFING_AT", "08:00")
        say(f"  {OK} enabled PC control, offline brain backup and the 08:00 briefing")
    if not os.environ.get("ATULYA_TELEGRAM_VOICE"):
        set_env_value("ATULYA_TELEGRAM_VOICE", "on")
        say(f"  {OK} Telegram replies follow your input: voice for voice notes, text for text")

    step("5. Dashboard")
    build_dashboard(args.yes)

    step("6. Health check")
    ready = doctor()

    serviced = False
    if args.service:
        step("7. Start by itself")
        serviced = install_service()

    say("")
    if ready:
        say(f"  {GREEN}{BOLD}Ready.{RESET} Start Atulya with:")
    else:
        say(f"  {YELLOW}Mostly ready — the items marked above still need attention.{RESET} Start with:")
    # The answer used to be "double-click start.bat" on every platform, which is
    # advice a Linux server cannot follow.
    start_hint = "double-click start.bat" if IS_WINDOWS else "./start.sh"
    say(f"\n    {BOLD}python -m atulya.sevak{RESET}    (or {start_hint})")
    if serviced:
        say(f"    {BOLD}sudo systemctl start {SERVICE_NAME}{RESET}    (installed, so it starts at boot)")
    say("")
    if not args.no_start and not args.yes and sys.stdin.isatty():
        if ask("Start Atulya now?", "y").lower().startswith("y"):
            return subprocess.call([sys.executable, "-m", "atulya.sevak"], cwd=ROOT)
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
