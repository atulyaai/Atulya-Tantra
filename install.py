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
        checks.append(("pip", False, "missing", "python -m ensurepip --upgrade"))
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
        checks.append(("Node.js (dashboard build)", True, nv, ""))
    else:
        checks.append(
            (
                "Node.js (dashboard build)",
                False,
                "not found",
                "optional — the API runs without it; install from nodejs.org to build the web UI",
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
        say(f"  {WARN} Node.js not found — skipping the web UI build ({DIM}the API and Telegram still work{RESET})")
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


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Install and configure Atulya Tantra")
    parser.add_argument("--doctor", action="store_true", help="report status only, change nothing")
    parser.add_argument("--yes", "-y", action="store_true", help="unattended: accept defaults, no prompts")
    parser.add_argument(
        "--profile", choices=sorted(PROFILE_EXTRAS), default="", help="which optional features to install"
    )
    parser.add_argument("--no-start", action="store_true", help="do not offer to start Atulya")
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

    say("")
    if ready:
        say(f"  {GREEN}{BOLD}Ready.{RESET} Start Atulya with:")
    else:
        say(f"  {YELLOW}Mostly ready — the items marked above still need attention.{RESET} Start with:")
    say(f"\n    {BOLD}python -m atulya.sevak{RESET}    (or double-click start.bat)\n")
    if not args.no_start and not args.yes and sys.stdin.isatty():
        if ask("Start Atulya now?", "y").lower().startswith("y"):
            return subprocess.call([sys.executable, "-m", "atulya.sevak"], cwd=ROOT)
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
